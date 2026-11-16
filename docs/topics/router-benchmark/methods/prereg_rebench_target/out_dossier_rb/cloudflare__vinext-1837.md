我已经查证了 14 处代码和测试，现在整理成档案。

# 仓库档案：global-error 自身抛错时没有最后兜底 UI

## 【1 题面要点】
- 要求：当 global error 组件自身失败时，返回内置的有效 HTML 兜底页，状态码是“预期的成功兜底状态”，并保留响应头和 cookie。
- 原文关键句：“Local error boundaries and framework navigation/control-flow signals must retain their existing semantics, and the original boundary exception must not be exposed.”
- 题面没有给复现步骤、期望输出和修法建议。“预期的成功兜底状态”没写具体数字。
- 现有 global-error 路径返回 200（`app-page-boundary-render.ts:455`），所以兜底状态大概率也是 200。
- “Interface: No new public interfaces” 表示不新增公共 API，只能在内部加东西。

## 【2 相关代码】
- `packages/vinext/src/server/app-page-boundary-render.ts:379` 的 `renderAppPageErrorBoundary` 是核心。
  - 它用 `resolveAppPageErrorBoundary` 选出错误组件（`app-page-boundary.ts:217`，global 时 `isGlobalError: true`）。
  - 它构造元素，global 时跳过布局（`:444`），然后返回 `renderAppPageBoundaryElementResponse`（`:447`，status 固定 200）。
- `app-page-boundary.ts:276` 的 `renderAppPageBoundaryResponse` 负责渲染 RSC 流和 HTML。
  - 它里面会调用 `createHtmlResponse` 并 await，该调用来自 `app-page-boundary-render.ts:264`。
  - 它在 `:293-299` 合并中间件头，在 `:307` 返回 HTML 响应。
  - 这里没有 try/catch，是 global-error 组件自身出错最先暴露的位置。
- `app-page-stream.ts:229` 的 `renderAppPageHtmlResponse` 构造 HTML 响应：设置 Content-Type、合并 `middlewareHeaders`、设置 Link。它没有处理 cookie。
- `app-fallback-renderer.ts:310-348` 的 `renderErrorBoundary` 是调用入口。
  - 默认的 global error 模块来自 `:166`，是 `DEFAULT_GLOBAL_ERROR_MODULE`。
  - 对应的组件是 `shims/default-global-error.tsx`（它输出 `<html id="__next_error__">`）。
- 调用链：`app-page-request.ts:457` 的 `buildAppPageElement` catch、`app-page-render.ts:816` 和 `:882`（RSC 错误后重渲染 global error）、`app-page-dispatch.ts:799/920`，最终走到 `app-rsc-entry.ts:709` 的 `renderErrorBoundaryPage`。
- 内置 HTML 先例：`app-page-execution.ts:292-319` 的 `buildMetadataRedirectHtmlResponse` 返回字符串形式的 `<!DOCTYPE html>`，并显式处理了 cookie（`:304-307`）。这是最接近的“保留 header 和 cookie”写法。

## 【3 并列与牵连】
- 两类调用都经过 `renderAppPageErrorBoundary`：
  - 页面错误；
  - RSC 流里已捕获的错误（`app-page-render.ts:882`）。
- 并列实现：`renderAppPageHttpAccessFallback`（`app-page-boundary-render.ts:301`）也包了 global error boundary，但题面只提 global error 组件自身抛错。
- RSC 请求路径（`isRscRequest`）和 HTML 请求路径要分别考虑。
  - RSC 请求走 `renderToReadableStream` 流，错误是流内的，不在 await 处抛出。
  - HTML 请求走 SSR。
- 成对方法：dev 和 prod 都用同一套（`app-rsc-entry.ts` 生成）。`app-page-route-wiring.tsx:1030` 还在正常渲染里嵌了 `ErrorBoundary fallback={globalErrorComponent}`，是另一处使用点。
- 改动会影响 `shouldRerenderAppPageWithGlobalError` 的重渲染路径，以及所有依赖 global-error 返回 200 的测试。

## 【4 现有测试与约定】
- `tests/app-page-boundary-render.test.ts:597-623`：global-error 渲染时 `status` 为 200，HTML 含 `data-boundary="global-error"`，不含布局。
  - 隐藏测试很可能加在同文件，构造一个会抛错的 `globalErrorModule`。
  - 文件内有 `createCommonOptions`（`:44` 附近）和一个假的 `handleSsr`。
- `tests/nextjs-compat/global-error.test.ts`：多处 `expect(res.status).toBe(200)`，生产环境不暴露原始消息（`:277` 断言 `not.toContain("server page error")`）。
- `tests/app-fallback-renderer.test.ts`、`tests/app-page-boundary.test.ts`、`tests/app-page-stream.test.ts` 也涉及相关行为。
- 参考实现：Next.js 的 `builtin/global-error.tsx`（vinext 已移植）。仓库里没有现成的“兜底 HTML”字符串规范，题面说的“built-in valid HTML fallback”要自己定义。
- 与题面不冲突，都是 200。

## 【5 边界与隐含要求】
- 要区分真错误和框架控制流信号（redirect、notFound、forbidden、unauthorized）。
  - 这些信号带 `digest`（见 `app-page-stream.ts:313`，`resolveAppPageSpecialError`）。
  - 它们必须原样重抛或交给原有处理，不能被兜底吞掉。
- 本地 `error.tsx` 的语义不变：只有 `isGlobalError` 路径才加兜底。
- “原始 boundary 异常不得暴露”：兜底 HTML 里不能含原始错误消息或堆栈。
  - 兜底 HTML 里也不能含 global-error 组件自身抛出的消息。
- 保留 header：中间件头、`Vary`、字体 `Link`。
- 保留 cookie：`getAndClearPendingCookies` 在 `buildMetadataRedirectHtmlResponse` 里有先例，但 `renderAppPageErrorBoundary` 的选项里没有这个字段。可能需要把它穿进去，或确认 cookie 已经在 `middlewareContext.headers` 里。
- 兜底 HTML 要有效：doctype、html、head 加 meta charset、body。需要考虑 nonce 和 CSP。
- 抛错时机有两种：
  - 创建响应时同步或异步抛出；
  - 流中途才报错，此时已无法换状态码。
  需要弄清哪种是“global error 自己失败”的主路径。
- 是否需要 `clearRequestContext()`，以及 RSC 请求是否也要兜底。
- 内置 `DefaultGlobalError` 自己抛错时也应走兜底，不能递归。

## 【6 改动规模】
- 预计 1 至 3 个源文件、几处局部修改。
  - 主要是 `app-page-boundary-render.ts` 的 `renderAppPageErrorBoundary`：加 try/catch，仅 global 分支，并新增一个兜底 HTML 构造函数。
  - 可能还要在 `app-fallback-renderer.ts` 传 cookie 回调。
  - 可能还要修改 `app-page-boundary.ts`。
- 属于局部修补，加一个小的新辅助函数，不贯穿多层。如果 cookie 必须穿参，会略微多几处签名改动。

## 【7 难点一句话】
难点是在哪一层捕获“global-error 组件自身失败”：这个错误可能在 SSR 流里才出现，而且要区分它与 redirect/notFound 这类带 digest 的控制流信号，同时保住 header 和 cookie（含待写 cookie 的来源）。题面没给具体复现，需要自己构造一个会抛错的 global error 模块来验证。