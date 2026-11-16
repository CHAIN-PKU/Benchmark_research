# 档案：Cron/后台会话在所属项目下不显示

## 【1 题面要点】
- 要求的行为：非空的 cron 或后台会话，如果已分配到某个项目，选中该项目时必须显示。
- 这类会话在以下视图中仍须隐藏：默认视图、未分配视图、空会话、无关项目的视图。
- 原文："The behavior must be consistent across supported session retrieval modes."
- 题面没有给复现步骤、期望输出或修法建议。
- 题面写 "No new interfaces are introduced."，所以不能新增对外接口。
- 题面没说"项目选中"这个信号怎么传给后端。

## 【2 相关代码】
- `api/models.py:2183` `_hide_from_default_sidebar(session)`：核心的隐藏判断。
  - `source_tag/source == 'cron'` 或 sid 以 `cron_` 开头时，无条件返回 True。
  - pre_compression_snapshot 是另一条分支，返回 `not _show_pre_compression_snapshot`。
  - 它没有任何"项目"概念，也没有参数。
- `api/models.py:2225` `_is_intentionally_background_sidebar_session`：同样的 cron 判断，在 `_preserve_messageful_sidebar_discoverability`（:2231）里使用。
  - 该函数会"救回"被过滤掉的非空行，但跳过后台会话。
- `api/models.py:2289` `_prefer_fuller_snapshots_for_sidebar`：:2306-2308 内联了一份 cron 判断。
- `api/models.py:2419` `all_sessions(diag)`：有两条检索路径，都调用 `_hide_from_default_sidebar`。
  - 索引路径：:2506-2507。
  - 全量扫描回退路径：:2545-2546。
  - 两条路径代码重复，要同步改。
  - `all_sessions` 无参数，调用点见 routes.py 的 :3523、:4424、:4428、:6249、:6984、:6991。
- `api/models.py:2712` `is_cron_session(sid, source_tag)`：按 source_tag 或 `cron_` 前缀判断。
- `api/models.py:2665` `ensure_cron_project()`：为每个 profile 建一个 "Cron Jobs" 项目。
- `api/models.py:3076-3128` `get_cli_sessions()`：读 state.db，用 `exclude_sources=None` 取行。
  - cron 行的 `project_id` 通过 `_cron_pid()` 赋为 Cron Jobs 项目。
  - 非 cron 行是 None。
- `api/routes.py:4420-4519` `GET /api/sessions`：
  - 取 `all_sessions()` 的结果。
  - 如果 `show_cli_sessions`，再并入 `get_cli_sessions()`，并在 :4455-4456 用 `_cron_hide` 剔除 cron。
  - 否则（:4459）调用 `_is_cli_session_for_settings`。
  - 随后做 profile 过滤、messaging 去重和 cli_cap。
- `static/sessions.js:3289-3297`：前端按 `_activeProject` 在客户端过滤 `project_id`。
  - NO_PROJECT_FILTER 对应 `!s.project_id`。
  - 请求不带项目参数（:472 只在创建会话时带 `project_id`）。
- `api/agent_sessions.py:347` `read_importable_agent_session_rows(exclude_sources=("cron","webui"))`：默认就排除 cron 行。
  - 这是另一层过滤（用于导入）。
- `api/routes.py:12141-12212` `_handle_session_import_cli`：给导入的 cron 会话赋 `cron_project_id`。
  - read_only 分支里 `project_id` 硬写 None（:12182）。

## 【3 并列与牵连】
- 并列实现（必须一起改）：
  - `all_sessions` 的索引路径和全量扫描路径。
  - `/api/sessions` 的 show_cli 分支和非 show_cli 分支。
  - 同一个"cron 判定"散落 4 处：:2187、:2227、:2307、`is_cron_session`。
- "多种检索模式"最可能指：
  1. `all_sessions` 的索引路径；
  2. `all_sessions` 的全量扫描路径；
  3. `/api/sessions` 在 `show_cli_sessions` 开/关两种设置下的行为。
  - 这是我的推测，题面没有明说。
- 影响面：
  - `_hide_from_default_sidebar` 的签名或语义变化，会影响 `_preserve_messageful_sidebar_discoverability`，因为它的 `visible` 和"后台"判断要保持一致。
  - `/api/sessions` 之后的 profile 过滤、`_keep_latest_messaging_session_per_source`、`_cap_recent_cli_sessions` 也会作用在放出来的 cron 行上。
  - `_handle_sessions_search`（routes.py:6977）也调用 `all_sessions`。
  - `api/session_discoverability.py` 是只读审计，调用 `all_sessions()`。

## 【4 现有测试与约定】
- `tests/test_gateway_sync.py:1518` `test_cron_sessions_hidden_from_sidebar_by_default`。
  - :1532 断言 `'cron_job123_20260427' not in ids, "Cron session should be hidden by default"`。
  - :1498 另有 `test_imported_cron_sessions_hidden_from_sidebar_by_default`。
  - 这些断言必须保持成立（"默认视图仍隐藏"）。
- `tests/test_gateway_sync.py:1542` 断言 `read_importable_agent_session_rows` 默认排除 cron，可通过选项带入。
- `tests/test_1079_cron_session_project.py`：
  - :57-70 `is_cron_session` 的行为；
  - :88 `get_cli_sessions` 只测"可调用、返回 list"；
  - :22 `ensure_cron_project` 创建的项目 name 是 "Cron Jobs"、颜色 `#6366f1`。
- 相关还有 `tests/test_issue1614_project_profile_filtering.py`（项目按 profile 隔离）、`tests/test_sidebar_unassigned_filter.py`、`tests/test_sidebar_first_turn_visibility.py`。
  - 这几个我只确认了文件存在，没读内容。
- 约定：cron 会话默认隐藏，同时自动归入 "Cron Jobs" 项目（#1079）。
  - 题面期望的是"选中该项目时可见"，与现有"无条件隐藏"冲突，要改的就是这点。
- 没有外部规范。

## 【5 边界与隐含要求】
- "非空"：`message_count` 与 `actual_message_count` 取其一，参考 `_sidebar_message_count`（:2194）。
  - 全量扫描路径里的 compact 是否带 `message_count` 需要核实。
- "已分配项目"：`project_id` 有值。
  - 要处理 `project_id` 是 Cron Jobs 项目，还是用户手动移到别的项目。
  - "无关项目"视图：该 cron 会话的 project_id 不等于选中项目时要隐藏。
- 未分配（cron 会话 `project_id` 为 None）仍隐藏。
- 空会话仍隐藏，包括 Untitled 0 消息的过滤（:2498）。
- 隐藏的是 cron 且已分配项目的行；pre_compression_snapshot 逻辑不能被破坏。
- profile 作用域：不同 profile 的 Cron Jobs 项目不同；放行后不能跨 profile 泄漏。
- `get_cli_sessions` 给 cron 行赋 `project_id`，但 all_sessions 索引里的 cron 会话是否带 `project_id` 取决于 `Session.compact`。
- 前端 `_activeProject` 过滤是客户端的。
  - 若后端本来就返回全部 cron 行，前端按 project 过滤即可；
  - 若后端过滤，则需要某种项目参数。
  - 如何传递"选中项目"是开放问题。
- 隐藏测试可能直接调用 `all_sessions()` 或 `/api/sessions`，并比较两种模式。

## 【6 改动规模】
- 大概 1-2 个文件：`api/models.py`，可能加 `api/routes.py` 和 `static/sessions.js`。
- 约 3-6 处：`_hide_from_default_sidebar`、`_is_intentionally_background_sidebar_session`、`_prefer_fuller_snapshots_for_sidebar` 的 cron 判断、`all_sessions` 两条路径、`/api/sessions` 的 `_cron_hide`。
- 多数是局部修补。
- 如果走"后端过滤"，要贯穿 路由→`all_sessions`→filter 多层；如果走"后端放行 + 前端过滤"，改动更小。

## 【7 难点一句话】
题面几乎没有规格，难在判断"项目选中"这个信号如何到达后端，以及要同时覆盖 `all_sessions` 的两条路径和 `/api/sessions` 的 CLI 合并分支，否则各模式行为不一致。