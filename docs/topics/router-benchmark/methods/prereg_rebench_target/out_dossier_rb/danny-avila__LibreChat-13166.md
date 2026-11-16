# 仓库档案：Anthropic 重复 web_search 工具名

我做了十几次搜索和阅读，没有用上游修法的记忆。有两点没能实证：`@librechat/agents` 里的合并逻辑没有读，Anthropic 的 `options.tools` 是否经过 `initializeAgent` 也没有端到端核对。

## 【1 题面要点】
- 要求的行为：LibreChat 的 web search 和 Anthropic 原生 web search 同时启用时，只暴露一个 `web_search` 工具，并且优先用 LibreChat 的定义。
- 限制：不影响无关工具，不影响其他 provider。
- 题面没给复现步骤、期望输出或修法建议。
- 关键句：“expose one `web_search` tool and prefer LibreChat's definition. Do not affect unrelated tools or other providers.”
- 接口：“No new public interfaces are introduced.” 也就是不新增导出，只改内部行为。
- 隐藏测试大概率调用 `initializeAgent`，或测某个内部辅助函数，断言 `tools` / `toolDefinitions` 里 `web_search` 只出现一次。具体入口题面没说。

## 【2 相关代码】
- `packages/api/src/endpoints/anthropic/llm.ts:296-302`
  - 原生工具在这里生成：`enableWebSearch` 为真时，`tools.push({type:'web_search_20250305', name:'web_search'})`。
  - 返回值是 `{tools, llmConfig}`（约 326 行），`tools` 就是 `options.tools`。
  - 这里不知道 agent 有没有启用 LibreChat 的 web_search。
  - 启用开关来自 `modelOptions.web_search`、`defaultParams`、`addParams`、`dropParams`（140、242、261、282 行）。
- `packages/api/src/agents/initialize.ts:829-847`（最可能的改动点）
  - 默认 `tools = options.tools?.length ? options.tools : structuredTools`。
  - 当 provider 是 OPENAI、AZURE 或 ANTHROPIC，且 `options.tools` 和 `structuredTools` 都非空时，执行 `tools = structuredTools.concat(options.tools)`。这里会直接产生重名。
  - Google/Vertex 有 `GOOGLE_TOOL_CONFLICT` 分支（833-838 行），这是“冲突”的先例，但处理方式是抛错，不是去重。
- `packages/api/src/agents/initialize.ts:678-695, 827, 932, 946`
  - `toolDefinitions`（LCTool 定义，事件驱动模式）和 `structuredTools`（工具实例）由 `loadTools` 返回。
  - 最终返回的 `InitializedAgent` 带 `tools` 和 `toolDefinitions`。
- `packages/api/src/agents/run.ts:868-917`
  - `toolDefinitions` 和 `tools: agent.tools` 原样交给外部 `@librechat/agents` 运行时，LibreChat 这边没有再合并或去重。
- `api/server/services/ToolService.js:504, 561, 803, 960`
  - `web_search` 是 native tool，受 capability 控制。

## 【3 并列与牵连】
- 重名可能出现在两条路径：
  - 实例路径：`structuredTools.concat(options.tools)`。
  - 事件驱动路径：`toolDefinitions` 里有 web_search，同时 `options.tools` 里有原生对象。此时 `structuredTools` 可能为空，`tools` 就只等于 `options.tools`（829-831 行）。
  - 这两条路径都要处理，否则 Anthropic 仍会拒绝。
- 原生工具是 `{type, name}` 对象，没有 LangChain 工具的 `.name` 约定，按名字过滤要兼容两种形态。
- OpenAI、Azure 的分支和 Anthropic 共用同一个 `else if`，改动要按 provider 限定为 `Providers.ANTHROPIC`。
- 其他 provider 的原生工具不能被碰：
  - `packages/api/src/endpoints/openai/llm.ts` 里有 web_search 相关处理。
  - `packages/api/src/endpoints/google/llm.ts` 也有。
- `packages/api/src/endpoints/openai/config.anthropic.spec.ts` 通过 openai/config 走 Anthropic 配置，也会产生原生 web_search。
- `packages/api/src/agents/added.ts:159` 和 `load.ts:72` 会在 ephemeral agent 上把 `Tools.web_search` 加进 `tools`，这是触发条件的来源，不是改动点。

## 【4 现有测试与约定】
- `packages/api/src/endpoints/anthropic/llm.spec.ts:1668`：`expect(result.tools).toEqual([{ type: 'web_search_20250305', name: 'web_search' }]);`
  - 说明 llm.ts 单独输出原生工具是既定行为。若改 llm.ts，这个断言会受影响。
- `packages/api/src/agents/__tests__/initialize.test.ts`
  - 745-1254 行有很多 `agent.tools = ['web_search']`，用 `loadTools` mock 检查调用参数，例如 787、820 行的 `toEqual([...])`。
  - 1271-1311 行是 `GOOGLE_TOOL_CONFLICT` 的测试，用 `mockGetProviderConfig` 注入 `tools: [{ google_search: {} }]`。隐藏测试很可能照这个模式，对 Anthropic 注入 `{type:'web_search_20250305', name:'web_search'}`。
  - 隐藏测试大概率在这个文件里，断言 `result.tools` 或 `toolDefinitions` 里只有一个 `web_search`。
- `packages/api/src/tools/definitions.spec.ts:221-237`：web_search 的 LCTool 定义包含 parameters。
- 约定上没有外部规范文件。唯一的外部约束是 Anthropic API 不允许重名工具，也不允许原生工具和自定义工具重名。
- 与题面期望没有冲突。唯一风险是 llm.ts 的现有测试，如果在那一层改就会受影响。

## 【5 边界与隐含要求】
- 只有 `name === 'web_search'` 的项被去重，其他工具和其他原生工具保留，顺序也尽量保持。
- 只对 ANTHROPIC provider 生效。OpenAI、Azure、Google、Vertex 行为不变。
- 如果 LibreChat 没启用 web_search，原生工具必须保留，否则会丢功能。
- 要判断“LibreChat 的 web_search 是否在场”，可以看 `structuredTools` 里的 `.name`、`toolDefinitions` 里的 `.name`，或 `agent.tools` 里的字符串。事件驱动模式下 `structuredTools` 可能为空。
- 需要给 `options.tools` 只剩一个或为空的情况兜底。如果过滤后 `options.tools` 为空，当前三元表达式会回退到 `structuredTools`，要确认结果仍然正确。
- Anthropic 原生 web_search 还会给 Vertex 加 beta header（`llm.ts:304-313`）。去掉原生工具后，这个 header 是否保留，是个小的取舍点，题面没提。
- 有的 `tools` 元素是 LangChain 工具实例，有的是纯对象，按名字读取时要防 undefined。

## 【6 改动规模】
- 预计 1 个源文件、1 到 2 处局部修补，主要在 `initialize.ts` 的 829-847 行附近：加一个按名过滤的小逻辑。
- 如果同时覆盖事件驱动的 `toolDefinitions` 路径，还要多一个判断分支。
- 不需要新增公开接口，也不贯穿多层。
- 另外要补测试：`initialize.test.ts` 里加一两个用例。

## 【7 难点一句话】
难点是找对去重位置，并同时覆盖 `structuredTools` 和 `toolDefinitions` 两条路径：llm.ts 看不到 LibreChat 工具，合并发生在 `initialize.ts`，而且改动必须限定在 Anthropic 和名为 `web_search` 的工具上。