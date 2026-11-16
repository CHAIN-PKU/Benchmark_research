**档案：`retain_recent_legal_suffix` 在 else 分支下重复归档用户消息**

**【1 题面要点】**
- 要求的行为：最近 N 条全是 assistant/tool 消息，而最后一条 user 消息在更早位置时，该 user 消息只能留在 kept 里，不能同时进 archive。
- 题面给了复现条件：消息数超过 `_RECENT_SUFFIX_MESSAGES`；最近 N 条没有 user；最后一条 user 在倒数第 11–15 条之间。
- 题面没给可运行的复现脚本，日志是空的。
- 期望的数值例子：`tail=100`，`latest_user=85`，`max=10`，期望 `cut = latest_user  # 应该是 85，不是 90`，`archive = tail[:85]`，`kept = tail[85:]`。
- 建议的修法："cut 值应该基于用户消息的实际位置，而不是简单的 len(tail) - len(kept)"。
- Interface 段给出新签名：`retain_recent_legal_suffix(self, max_messages) -> tuple[list[dict], int]`。含义是返回被丢弃的消息列表，以及其中已处于 consolidated 前缀的数量，调用方据此只归档新消息。
- 这个签名变更在正文里只字未提，只出现在 Interface 段，但隐藏测试很可能按它断言。

**【2 相关代码】**
- `nanobot/session/manager.py:272-312`，`Session.retain_recent_legal_suffix`，当前返回 None。
  - 283-285：tail 里有 user，就从第一个 user 开始截。
  - 286-295：else 分支，找整个会话里最后一个 user，取 `messages[latest_user: latest_user+max_messages]`。
  - 298-307：`find_legal_message_start`，再做硬上限。
  - 309-311：`dropped = len(messages) - len(retained)`，`last_consolidated -= dropped`，只是个数。
- `nanobot/agent/memory.py:779-845`，`Consolidator.compact_idle_session`。
  - 802-813：用 probe session 调用该方法，然后 `cut = len(tail) - len(kept); archive_msgs = tail[:cut]`。这就是 bug 点。
  - else 分支下 kept 是窗口 `[latest_user : latest_user+N]`，而不是 tail 的尾部。`len(tail)-len(kept)` 大于 `latest_user`，所以 `tail[:cut]` 会包含 user 消息，同时 kept 也包含它，造成重叠。
  - 同时，window 之后的消息（latest_user+N 往后）既不在 kept 也不在 archive，直接丢失。
- `manager.py:314-342`，`enforce_file_cap`：`dropped_count = before_count - len(messages)`，`dropped = before[:dropped_count]`，同样假设丢弃的是前缀。
- `nanobot/cli/commands.py:1032`：heartbeat 调用，忽略返回值。

**【3 并列与牵连】**
- 调用点共 4 处：`memory.py:810`、`manager.py:326`、`commands.py:1032`、`autocompact.py` 通过 `compact_idle_session`（`autocompact.py:56`）间接调用。
- `enforce_file_cap` 有同样的前缀假设。else 分支下，丢弃的不是 `before[:dropped_count]`，而是前缀加后缀。归档的内容会错位。
- 测试里复制了真实逻辑：`tests/agent/test_auto_compact.py:61-108` 的 `_fake_compact` 同样写着 `cut = len(tail) - len(kept)`，且依赖返回 None。隐藏测试很可能更新这个 fake，改用新返回值。
- 新返回值的第二项是 `already_consolidated`，应对应 `enforce_file_cap` 里的 `min(before_last_consolidated, dropped_count)`。
- 其他调用方不需要使用返回值，但新签名不能破坏它们。

**【4 现有测试与约定】**
- `tests/agent/test_session_manager_history.py:132-181`：
  - `:139-141`：`len(messages)==4`，`messages[0]["content"]=="msg6"`。
  - `:153`：`last_consolidated == 1`。
  - `:164-165`：`max=0` 时 `messages == []` 且 `last_consolidated == 0`。
  - `:180-181`：`history[0]["role"]=="user"` 且 `content=="keep"`。
  - 这些测试都没有使用返回值，所以改成返回元组不会让它们失败，只要副作用保持不变。
- `:523-540`：硬上限用例，只断言 `len(messages) <= 6`。
- `tests/agent/test_auto_compact.py:205-226`：`enforce_file_cap` 的两个用例（`skips_archive_when_dropped_prefix_already_consolidated` 和 `archives_only_unconsolidated_dropped_prefix`）。重构时要保持它们通过。
- 另有 `test_auto_compact.py:297`、`:320`、`:550` 等多处断言 `len(session_after.messages) == _RECENT_SUFFIX_MESSAGES`。
- 约定是 `get_history` 的逻辑（`manager.py:243-261`）：从 user 开头，再用 `find_legal_message_start` 保证工具调用边界。
- 与题面不冲突，但目前没有任何测试覆盖 else 分支下的归档重叠。

**【5 边界与隐含要求】**
- else 分支的 window 之后是否还有消息：窗口 `[latest_user : latest_user+N]` 之后的消息（题面例子里 85+10=95，剩 95–99）既没被保留也没被归档。题面的例子却写 `kept = tail[85:]`（15 条，超过 max=10）。这与硬上限 `len <= max_messages` 冲突，需要决定取舍。
  - 若按硬上限再截一次，后面的 `retained[-max_messages:]` 会改变起点，user 消息可能又被切掉。
  - 这是最不明确的点。
- `last_consolidated` 的偏移：dropped 里已 consolidated 的数量要正确计算，丢弃内容不连续时需要按下标而非个数算。
- `max_messages <= 0` 时 `clear()`：返回值应是全部消息，已 consolidated 数为 `min(last_consolidated, len)`。
- `len(messages) <= max_messages` 时提前返回：应返回 `([], 0)`。
- `find_legal_message_start` 在窗口前端裁掉孤立 tool 结果后，被裁掉的消息也应算进 dropped。
- 没有任何 user 的会话：else 分支里 `latest_user is None`，retained 保持为 tail 的尾部。
- probe 的 `last_consolidated=0`，所以 `compact_idle_session` 里的第二项恒为 0。

**【6 改动规模】**
- 2 个核心文件：`manager.py`（方法加返回值，并修正 `enforce_file_cap`）和 `memory.py`（`compact_idle_session` 用返回的 dropped 列表代替 `tail[:cut]`）。
- 另外要更新测试里的 `_fake_compact`，可能还要补测试。
- 总共约 3–4 处修改，局部修补，不需要新增结构，但需要改变方法的返回约定。

**【7 难点一句话】**
难在 else 分支的保留窗口不是尾部，所以丢弃的消息是前缀加后缀、并不连续。题面例子（kept 15 条）和硬上限还互相矛盾，要决定怎么处理窗口之后的消息，还要按 Interface 的新返回签名把 `dropped` 列表和 `already_consolidated` 数量对准，隐藏测试大概率就断言这两项。