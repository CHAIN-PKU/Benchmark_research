**【1 题面要点】**
- 要求：`openai.realtime.RealtimeModel` 增加 `reasoning` 参数，例如 `reasoning={"effort": "low"}`，并随 session 配置发给 OpenAI。
- 题面给了用法示例，没有给复现步骤和期望输出，也没有说怎么修。
- 题面只给出一个可能的做法：“patching the plugin locally to add `reasoning` to the session update payload”。
- 取值范围：`minimal`、`low`、`medium`、`high`、`xhigh`。
- 题面写 “No new interfaces are introduced”，但构造函数参数本身就是新的公共接口。
- 题面没说 `update_options` 是否也要支持。

**【2 相关代码】**
文件：`livekit-plugins/livekit-plugins-openai/livekit/plugins/openai/realtime/realtime_model.py`
- `_RealtimeOptions` dataclass（约 218-239 行）：保存会话选项，需要新增 `reasoning` 字段。
- `RealtimeModel.__init__` 有两个 `@overload`（约 270-322 行）和一个实现（约 324-477 行）：
  - 需要给两个 overload 和实现加 `reasoning` 参数。
  - 还要更新 docstring（约 356-374 行）。
  - 在 `_RealtimeOptions(...)` 构造处（约 455-477 行）传入该值。
- `RealtimeModel.update_options`（约 650-708 行）：模型层更新选项，并转发给各个 session。
- `RealtimeSession._create_session_update_event`（约 1161-1195 行）：构造初始 `RealtimeSessionCreateRequest`，是 `reasoning` 真正进入 payload 的地方。
- `RealtimeSession.update_options`（约 1205-1294 行）：发送增量的 `session.update`。
- `models.py:61-64`：`RealtimeModels` 字面量已包含 `gpt-realtime-2`，不用改。

**【3 并列与牵连】**
- 同一个选项要在 5 个位置保持一致：`_RealtimeOptions`、`__init__`（含 overload）、`_create_session_update_event`、模型层 `update_options` 和 session 层 `update_options`。
- `with_azure`（约 540-648 行）是另一个工厂方法。它把参数逐个转发给 `__init__`，可能也要加 `reasoning`，我没有逐行核对。
- Azure 旧版 API 的转换函数 `_oai_session_to_azure`（约 150-201 行）是逐字段映射。`reasoning` 不在映射里，所以旧版 Azure 会静默丢弃它。这是个取舍点。
- xAI 等插件可能复用这个 realtime 实现，我没有核查。
- `update_options` 的既有模式是：先和当前值比较，有变化才设置 `session.xxx` 并把 `has_changes` 置真。

**【4 现有测试与约定】**
- `tests/test_realtime/test_realtime.py:27-45` 只有 `_openai_model()`、`_azure_model()`、`_xai_model()` 三个构造函数，其余是需要联网的集成测试。
  - 断言都是内容类的，例如 `assert "pineapple" in text.lower()`（136 行）。
  - 文件里没有任何 `reasoning` 相关内容。
- 没找到现有的离线测试来断言 session update payload。隐藏测试很可能是：构造 `RealtimeModel(reasoning=...)`，调用 `_create_session_update_event()` 检查 payload，或检查 `update_options`。
- 外部规范是 OpenAI Realtime API 的 `session.reasoning.effort`。
  - 依赖是 `openai[realtime]>=2`（`pyproject.toml:26`）。
  - 我没能确认已安装的 openai SDK 里 `RealtimeSessionCreateRequest` 是否带 `reasoning` 字段，全盘 glob 超时了。
  - 如果 SDK 没有该字段，要用 `model_construct`、`extra` 或升级依赖来绕过。
- 仓库里没有可参考的实现。`models.py:296` 的 `_supports_reasoning_effort` 属于 chat LLM，不是 realtime。

**【5 边界与隐含要求】**
- 默认值应为 NOT_GIVEN/None。不传时 payload 不能出现 `reasoning` 键，否则会破坏 `gpt-realtime` 等不支持推理的模型。
- 参数是 dict（如 `{"effort": "low"}`），可能还要接受 SDK 的类型对象，并判断是否做 effort 取值校验。
- `update_options` 要支持，且需要变化检测。
- 要决定 Azure 旧格式路径如何处理。
- 要决定对非 `gpt-realtime-2` 模型是否告警或忽略。
- 断线重连时会重发 `_create_session_update_event`，所以 `reasoning` 必须存在 `_opts` 里，不能只存在一次性的增量更新里。

**【6 改动规模】**
- 主要改 1 个文件，约 6-8 处局部修改，不需要新增结构，也不贯穿多层。
- 可能附带 1 个测试文件。如果 SDK 类型不支持，才会连带改 `pyproject.toml`。

**【7 难点一句话】**
改动本身很机械。难点在于把所有入口都覆盖到：两个 overload、`with_azure`、两层 `update_options` 和初始 payload。同时要确认已安装的 openai SDK 能序列化 `reasoning` 字段，并保证不传时 payload 完全不变。