# 仓库档案：`createAgenticSystem` 重复注册 `activate_skill`

## 【1 题面要点】
- 要求的行为：`createAgenticSystem(FooAgent.class)` 在单个 agent、`@ToolProviderSupplier` 返回 `Skills...toolProvider()` 时不能抛 `IllegalConfigurationException: Duplicated definition for tool: activate_skill`。
- 复现：题面给了完整代码，用 `@Agent` 接口加静态 `@ToolProviderSupplier` 和 `@ChatModelSupplier`。题面还提到 `agentBuilder(FooAgent.class).build().test()` 这条路径，但被注释掉了。
- 期望：“The agentic system should run successfully, properly deduplicating tools (including the built-in `activate_skill` tool) when registering non-dynamic `ToolProvider` instances.”
- 题面自带的原因分析：“`createAgenticSystem` registering non-dynamic `ToolProvider` instances multiple times.”
- 题面没有给修法。
- Interface 段只说新增或调整 `createAgenticSystem(Class<T>, AgentConfigurator)`，“resolves the default chat model from the agent class and deduplicates tool registrations”。
- 注意：这个重载在快照里已经存在，在 `AgenticServices.java:318-321`，且已经用 `declarativeChatModel`。所以签名本身不需要新增，要改的是行为。

## 【2 相关代码】
- `langchain4j-agentic/.../AgenticServices.java:330-347`：最终的 `createAgenticSystem(cls, chatModel, configurator)`。
  - 非组合 agent 时，先执行 `agentBuilder(agentServiceClass)`（第 337 行），再执行 `configureAgent(agentServiceClass, chatModel, agentBuilder, agentConfigurator)`（第 338 行）。
- `agent/AgentBuilder.java:131-141`：构造函数里已经调用 `configureAgent(agentServiceClass, this)`。
  - 这个调用走 `DeclarativeUtil.java:46-48`，即 `allowNullChatModel=true` 的版本。
- `declarative/DeclarativeUtil.java:54-149`：私有 `configureAgent`。
  - 第 55-66 行处理 `@ToolsSupplier`。
  - 第 68-73 行处理 `@ToolProviderSupplier`，调用 `agentBuilder.toolProvider(...)`。
  - 第 75-140 行处理 retriever、memory、chat model。
  - 第 142-146 行处理 listener。
  - 第 148 行调用 configurator。
- `AgentBuilder.java:121, 382-394`：`toolProviders` 是 `ArrayList`，`toolProvider()` 用 `add` 追加，没有去重。
  - 第 304-305 行把它们交给 `aiServices.toolProviders`。
- `langchain4j/.../ToolService.java:346-403`：`createContextFromStaticToolsAndProviders`。
  - 非 dynamic 的 provider 逐个 `provideTools` 再 `addTools`。
  - `addTools`（第 397-398 行）发现同名工具就抛 “Duplicated definition”。
- `langchain4j-skills/.../Skills.java:198`：`isDynamic()` 在有 skill 级工具时返回 true，否则 false。
  - 本题里 skill 没有工具，所以 provider 是非 dynamic，会进入 `addTools`。

**根因（已从代码确认）：** `agentBuilder(cls)` 的构造函数已经调用一次 `configureAgent`，`createAgenticSystem` 又调用一次。`@ToolProviderSupplier` 的 provider 被 add 了两次，每次 `provideTools` 都返回 `activate_skill`，于是在 `ToolService` 里重复。

## 【3 并列与牵连】
- 同样的双重调用在 `AgenticServices.java:597-598`（`createSubagent`）。
  - 它先 `agentBuilder(subgentClass)`，再 `configureAgent(...)`。
  - 声明式的子 agent 带 `@ToolProviderSupplier` 也会中招，必须一起改。
- 同一问题也影响：
  - `@ToolsSupplier`：对象工具重复添加。当前不抛异常，是因为 `tools(...)` 大概是覆盖赋值，需要确认。
  - `@ContentRetrieverSupplier`、`@RetrievalAugmentorSupplier`、memory、`chatModel`、listener：重复调用大多是覆盖，无害。
  - `listener`：`agentBuilder.listener(...)` 可能是追加，会重复。
- 所以 `toolProvider` 是唯一会报错的点，但 listener 等也可能被重复注册。
- 直接用 `agentBuilder(FooAgent.class).build()` 只调用一次 `configureAgent`，不受影响。题面注释里的这条路径本身是好的。
- 有两种可行的修法：
  - 在 `AgentBuilder.toolProvider(...)` 里对同一实例去重。
  - 避免重复调用 `configureAgent`，例如让构造函数不调用，或让 `createAgenticSystem` 只做 chatModel 和 configurator 部分。
- 第二种会牵涉 `AgentBuilder` 构造函数的其他调用方：`AgenticServices.agentBuilder(Class)` 的公开用法。
- 若在第一种修法里按“工具名”去重，需要先调用 `provideTools`，会碰到 `ToolProviderRequest` 的构造问题，较复杂。

## 【4 现有测试与约定】
- `DeclarativeAgentIT.java:745-766`：`@ToolsSupplier` 返回 `bankTool` 或 `new Object[]{bankTool}`。
  - 这些测试经 `createAgenticSystem` 走到子 agent，当前能通过，说明重复添加对象工具没有被 `ToolService` 检出。
  - 子 agent 路径是 `createSubagent`（第 597-598 行）。
- `DeclarativeAgentIT.java:180`：`new AgenticServices.AgentConfigurator(ctx -> {...}, ...)`，是 configurator 的用法。
- `ChatSupplierParameterResolverTest.java:151, 200, 236, 258`：`createAgenticSystem(X.class, DUMMY_MODEL)`。
  - 这些调用走 chatModel 重载，修改后不能破坏。
- 没有找到任何测试覆盖 `@ToolProviderSupplier`。仓库里只在 `docs/docs/tutorials/agents.md` 提到。
- `ToolProvider.isDynamic()` 在 `ToolProvider.java:42`，默认 false。
- `ToolService.java:398` 和 `ToolProviderResult.java:146` 对重名一律抛错，这是既有约定，与题面“去重”不冲突，修复应发生在 agentic 层。
- 隐藏测试很可能：
  - 用 mock `ChatModel` 对带 `Skills` provider 的 agent 调用 `createAgenticSystem`，断言不抛异常，且请求里 `activate_skill` 只出现一次。
  - 或者在子 agent 场景下做同样的断言。

## 【5 边界与隐含要求】
- `@ToolProviderSupplier` 在顶层 agent、子 agent（sequence、supervisor 等）和带 configurator 的路径里，每个 provider 都只能被注册一次。
- 用户通过 configurator 或 `agentBuilder.toolProvider(...)` 自己再添加的 provider 不应被误去重。
- 同一个 provider 实例被显式添加两次是否应该去重：这是语义决定，题面倾向去重。
- 有 skill 级工具时 `isDynamic()` 为 true，走另一条路径，不应被破坏。
- `@ToolsSupplier` 和 `@ChatModelSupplier` 的行为保持不变。
- `chatModel` 为 null 且没有 supplier 时，原来的 `IllegalArgumentException`（`DeclarativeUtil.java:135`）仍应抛出。
  - 构造函数那次调用用的是 `allowNullChatModel=true`，如果去掉第二次调用，这个校验就丢了。
- 构造函数里的 `configureAgent` 先于 `name`、`description` 等字段赋值（第 143 行之后），顺序可能影响 configurator。

## 【6 改动规模】
- 主要文件 1-2 个：`AgenticServices.java`（第 337-338 行和第 597-598 行共两处），以及 `AgentBuilder.java` 或 `DeclarativeUtil.java` 的小改动。
- 属于局部修补，不需要新增结构，也不贯穿多层。
- 另外需要新增一个测试。

## 【7 难点一句话】
根因很直白（`configureAgent` 被构造函数和 `createAgenticSystem`/`createSubagent` 各调用一次），难点是选一个既不丢掉 chatModel 必填校验、也不改变 `agentBuilder(Class)` 公开行为、并且同时覆盖子 agent 路径的去重方案。