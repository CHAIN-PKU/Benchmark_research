# 仓库档案：team.acontinue_run 丢失 dependencies / session_state

## 【1 题面要点】
- 期望行为：团队暂停后，用 `acontinue_run(run_id, session_id, requirements, stream=True, user_id, dependencies=...)` 恢复。成员工具 `group_del_stock(..., run_context: RunContext)` 里的 `run_context.dependencies["user_token"]` 或 `run_context.session_state["user_token"]` 应该有值，实际是 None。
- 题面给了复现代码，没有给期望输出，也没有测试。
- 题面给了修法线索，原句是："in _aroute_requirements_to_members_stream, The run_context has not been restored"，链接指向 `team/_run.py#L5145`。
- 题面只点名了异步流式一个函数，没提另外三个变体。
- 题面把 `dependencies=session_state` 传给 `acontinue_run`。期望里同时写了 dependencies 和 session_state，没有说哪个必须保证。

## 【2 相关代码】（均在 `libs/agno/agno/team/_run.py`）
- `_route_requirements_to_members` :4810，同步非流式。
- `_route_requirements_to_members_stream` :4903，同步流式。
- `_aroute_requirements_to_members` :5015，异步非流式，内部有 `_continue_member` 闭包 :5041，用 `asyncio.gather` 并发。
- `_aroute_requirements_to_members_stream` :5110，异步流式，即题面所指。
- 这四个函数都接收 `run_context`，但只拿它去调 `_find_member_route_by_id(team, member_id, run_context=run_context)`（:4837、:4936、:5042、:5146）。
- 调用成员续跑时，只传 `run_response=` 或 `run_id=`、`requirements=`、`session_id=`（流式再加 `stream`、`stream_events`、`yield_run_output`）。
  - 具体位置：同步 :4870–4881；同步流式 :4961–4977；异步 :5069–5079；异步流式 :5171–5187。
  - `run_context`、`dependencies`、`user_id`、`session_state`、`metadata`、`knowledge_filters` 都没有传。
- 团队侧调用点：
  - 同步 `_continue_run` 约 :5511 和 :5521。
  - 异步非流式 :6736。
  - 异步流式 :7068。
- 团队 `acontinue_run` 构造 `run_context`：约 :6539。
  - 构造时 `session_state={}`，`dependencies=opts.dependencies`，`user_id=user_id`。
  - 同步版在 :5418 附近，同样是 `session_state={}`。
- 成员侧入口 `Agent.acontinue_run`（`agent/agent.py:1611`）和 `continue_run`（:1535）：
  - 签名有 `user_id`、`run_context`、`dependencies`、`metadata`、`knowledge_filters`，但**没有** `session_state` 参数。
  - 转发到 `agent/_run.py` 的 `acontinue_run_dispatch`（:3561）。
- `_acontinue_run`（`agent/_run.py:3876`）：
  - 若 `run_context.dependencies is not None`，就解析依赖。
  - 用 `load_session_state(...)` 从 session 取 session_state，再 `_initialize_session_state`。
  - 所以成员的 `run_context` 必须由调用方带入，不传就在成员内部新建，dependencies 是空的。

## 【3 并列与牵连】
- 四个 route 函数是同一模式的复制粘贴，同步/异步、流式/非流式各一份。
  - 只修题面点名的 :5145 附近，另外三个仍会丢上下文。
  - 每个函数内都有「有 `_member_run_response`」和「回退到 `run_id`」两条分支，共 8 个成员续跑调用点，都要补。
- 团队 `_continue_run` 同步/异步、流式/非流式的构造 `run_context` 的代码也是各自一份（:5418、:6539 及流式版）。
- 成员的 `session_state`：
  - 成员 `continue_run` 没有 `session_state` 参数。
  - 要让成员看到团队的 session_state，要么通过 `run_context` 传入，要么新增参数。
  - 成员侧用 `run_context.session_state` 与 session 合并。
- 对比首次 run 的委派路径：
  - 委派用 `session_state=run_context.session_state`，见 :6130 等。
  - `delegate_task_to_member` 的 `grep` 没有直接命中 `dependencies=run_context`。这点我没有查实，委派时成员是否收到 dependencies 需要再核对。
- 嵌套团队：路由到子团队时，子团队也走 `continue_run`，所以 `run_context` 的传递需要向下贯穿。
- 链式 HITL（成员再次暂停，`_propagate_member_pause`）：重新恢复时同样依赖这里传递的上下文。

## 【4 现有测试与约定】
- `tests/unit/team/test_continue_run_requirements.py` 里没有直接测四个 route 函数的真实路径。
  - :196–246 测 `_find_member_route_by_id`。
  - :636–666 的 gather 测试只是**复刻过滤逻辑**，不调用真实函数，例如 `assert len(member_results) == 2`。
  - :397 的注释提到 route 函数追加新需求，仍是模拟。
- 没有现成断言覆盖「成员续跑收到 dependencies/session_state」。隐藏测试很可能 mock `member.continue_run/acontinue_run`，断言收到的 kwargs，如 `dependencies`、`user_id`、`run_context`，或者用真实 Agent 的工具读取 `run_context`。
- 约定：
  - 团队 `acontinue_run` 里 `if dependencies is not None: run_context.dependencies = opts.dependencies` 的覆盖规则。
  - 成员 `acontinue_run` 的签名里有 `run_context` 和 `dependencies`，说明传 `run_context=` 或 `dependencies=` 都可行。
  - 外部规范：没有。
- 与题面不冲突。

## 【5 边界与隐含要求】
- 流式、非流式，同步、异步四个变体都要一致。
- 带 `_member_run_response` 与回退到 `run_id` 两条分支都要传。
- 用户只传 `dependencies`，不传 `session_state`：
  - 团队的 `run_context.session_state` 是 `{}`。
  - 题面期望里写的 `session_state["user_token"]`，需要从 session 里恢复。
  - 这个我没有核实，是风险点：`acontinue_run` 里是否会从 DB session 载入 session_state 再传给成员。
- 无 DB 的场景：session 不可用，只能依赖传入的 `run_context`。
- `run_context` 是团队的，里面的 `run_id` 是团队 run id。直接共享给成员，成员的 `run_id` 可能被污染。
  - 更稳妥的是复制一份，按成员的 run 调整 `run_id`、`session_id`，再传入。
  - 这是推断，没有查证。
- 多个成员并发（`asyncio.gather`）时共享同一个 `run_context` 对象可能互相覆盖 session_state。
- 成员自身配置的 dependencies 与团队传入的合并规则（谁覆盖谁）。
- `user_id` 也需要传给成员，否则成员读取 session 会用错用户。

## 【6 改动规模】
- 主要改 1 个文件 `team/_run.py`。
- 4 个 route 函数，共约 8 个成员续跑调用点，各补传若干参数，改动形式相同。
- 可能还要改 `agent/agent.py` 与 `agent/_run.py`（若要给成员加 `session_state` 参数），以及团队构造 `run_context` 时从 session 恢复 `session_state`（约 2–4 处）。
- 总体是局部修补，不新增结构，没有跨层贯穿。

## 【7 难点一句话】
难点不在改法本身，而在题面只点了一个函数，实际是四个函数、八个调用点；还要弄清 `session_state` 该从哪里恢复、怎么传给没有 `session_state` 参数的成员，并避免共享 `run_context` 的副作用。