**档案：`jarvis agents list` Traceback（rich 标记错误）**

说明：issue 只给了表面现象。真正的底层异常（`exc`）内容未知，因此我没法确定隐藏测试具体会让哪个异常触发。

**【1 题面要点】**
- 期望行为：`jarvis agents list` 在重启后或模型卸载后仍应正常列出表格，示例为 `b0e6dece007b │ My Assistant │ deep_research │ idle │ 0 │ 0`。
- 复现步骤：先 `agents ask`，等 ollama runner 退出，再 `agents list`，得到 Traceback。
- 题面没有给期望输出以外的修法建议。
- 关键 Traceback：`agent_cmd.py line 91, in list_agents: console.print(f"[red]Error: {exc}[/red]")` → `rich.errors.MarkupError: closing tag '[/red]' at position 65 doesn't match any open tag`。
- 也就是说，真正出错的是 `except` 分支。`list` 内部先抛了一个异常，异常信息里带有方括号，被 rich 当成标记解析，于是在报错处理里又崩了一次。
- 题面没有说明第一个异常是什么。

**【2 相关代码】**
- `src/openjarvis/cli/agent_cmd.py:52-91`，`list_agents`：
  - 第 55 行 `Console(stderr=True)`。
  - 第 57-58 行 `_get_manager()` 与 `mgr.list_agents()`。
  - 第 72-73 行对每个 agent 调 `list_tasks`、`list_channel_bindings`。
  - 第 74-85 行 `status_style` 字典，状态不在字典里时取 `""`，生成 `[]x[/]`。
  - 第 90-91 行 `except Exception as exc: console.print(f"[red]Error: {exc}[/red]")`，这是直接崩溃的位置。
- `src/openjarvis/agents/manager.py:107-149`，`AgentManager.__init__`：
  - 连接 sqlite，设置 WAL，建表，跑迁移。
  - `clear_stale_running` 默认 False。
  - 第 140-147 行的注释说明 `list` 曾因扫描 running→idle 而误报。
- `manager.py:211` `list_agents`，`:749` `_row_to_agent`（`json.loads(config_raw)`），`:772` `_row_to_task`，`:786` `_row_to_binding`：这些是可能抛出带方括号异常信息的位置。
- `_get_manager`（`agent_cmd.py:13-24`）读取 `load_config()` 和 `config.agent_manager.db_path`。

**【3 并列与牵连】**
- `agent_cmd.py` 内有 11 处同样写法 `console.print(f"[red]Error: {exc}[/red]")`：
  - 位置为 `create`(111)、`info`(141)、`tasks`(163)、`pause`(176)、`resume`(189)、`delete`(202)、`bind`(233)、`channels`(258)、`search`(291)、`templates`(319)，加上 `list`(91)。
  - `info` 还有 `Agent not found: {agent_id}`(123)，`search` 同样有(276)，这两处也插入了用户输入。
- 同样写法还出现在 `src/openjarvis/cli/` 的 20 个文件里，共 76 处，包括 `skill_cmd`、`operators_cmd`、`compose_cmd`、`optimize_cmd`、`connect_cmd` 等。
- `info` 里还有 `console.print(f"    [{t['status']}] ...")`(134)，会把 `[idle]` 当成标记，且任务描述也被当成标记解析。
- `console.print(f"  Memory: {a['summary_memory'][:100]}...")`(129)、`{a['name']}`(125) 和 `{b['config']}`(139) 同样会被标记解析。
- `table.add_row(a["name"], ...)` 里 Table 单元格也按标记渲染：agent 名称带 `[x]` 会出问题。
- 仓库内目前没有统一的转义辅助函数。`init_cmd.py:11` 用了 `rich.markup.escape`。`_banner.py` 用了 `markup=False`。
- 若要全面修复，需要在整个 CLI 层加转义。最小修复是 `list`，以及 `agent_cmd.py` 里同类的几处。

**【4 现有测试与约定】**
- `tests/cli/test_agent_cmd.py` 目前只有 `--help` 测试，例如 `:11-13`：`assert result.exit_code == 0`，以及 `:22-23`：`assert "list" in result.output`。没有针对 `list` 行为或异常路径的测试。
- 另有 `tests/cli/test_ask_agent.py` 等文件匹配了 agents 相关关键字，我没有逐个读，也没有看测试里 `CliRunner`/mock 的用法。
- 约定：`init_cmd.py:462` 用 `escape(...)` 包裹不受信文本。
- 与题面期望没有冲突。但“正确行为”没有规范来决定：是只转义错误文本，还是同时找出并修复底层异常，隐藏测试怎么写，我从仓库里看不出来。

**【5 边界与隐含要求】**
- 隐藏测试很可能 mock `AgentManager.list_agents`，或让 `_get_manager` 抛出带方括号的异常，例如 `RuntimeError("bad [/red] tag")` 或 `"[Errno 2]"`，然后断言：
  - 不抛 `MarkupError`；
  - 输出里包含原始错误文本。
- 因为 `Console(stderr=True)`，测试要用 `CliRunner(mix_stderr=True)`，或者检查 `result.output` 或 `capsys`。我没有核实。
- 转义后输出里含 `\[` 吗？`rich.markup.escape` 会转义 `[` 后面跟字母的情况，输出时显示正常。
- `status_style` 为空时 `[]...[/]`：`[]` 不是合法标记，应该不会触发错误，但我没有验证。
- 题面里的真实原因：为什么“第二次之后 list 失败”？没有查明。可能是 sqlite 锁、WAL，或 `list_tasks`/`_row_to_*` 解析 JSON 失败。仓库内没有看到相关线索，只有 manager 的注释提到 running 状态。
- 退出码：当前吞掉异常、退出码为 0。修复后是否应非零，题面没说。

**【6 改动规模】**
- 最小改动：1 个文件（`agent_cmd.py`）、1 处（第 91 行）。
- 稳妥改动：`agent_cmd.py` 内约 11 处，加 `from rich.markup import escape`。
- 若要覆盖全部 CLI：20 个文件、约 76 处，机械性替换，不涉及新结构。
- 若还要找出并修复底层异常（题面暗示但未证实），则要深入 manager 或 DB 层，范围更大且不确定。

**【7 难点一句话】**
修补点本身很局部（对 `{exc}` 做转义），难处在于题面没说明底层异常是什么，以及隐藏测试要的是只修标记转义，还是同时修掉让 `list` 失败的底层原因，而这一点仓库里查不出来。