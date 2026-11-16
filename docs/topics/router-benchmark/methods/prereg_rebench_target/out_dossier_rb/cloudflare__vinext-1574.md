**档案：Pages Router gSSP 响应缺默认与用户设置的 `Cache-Control`**

本档案基于以上阅读和搜索整理。我没有跑测试，也没有找到题面所说的 Next.js 测试 `test/e2e/getserversideprops/test/index.test.ts` 的本地副本。

**【1 题面要点】**
- 要求的行为：
  - gSSP 页面的 HTML 响应默认带 `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate`。
  - 用户在 gSSP 里用 `res.setHeader('Cache-Control', …)` 设置的值要原样保留到最终响应。
- 现状：测试得到 `null`，即没有默认头，用户设置的头也被丢掉。
- 题面没有给可运行的复现步骤，也没有期望输出之外的样例。
- 题面的建议：
  - 先在 vinext 自己的测试里复现："Add a Pages Router gssp page and assert the response carries the default `Cache-Control` header; add a second page that overrides it via `res.setHeader`"。
  - "set `Cache-Control: private, no-cache, no-store, max-age=0, must-revalidate` unless the user set it explicitly"，题面写的是 "in deploy mode"。
  - "Make sure headers set during gssp dispatch are forwarded to the final HTTP response."
- 题面说 "No new interfaces"。

**【2 相关代码】**
- `packages/vinext/src/server/pages-page-response.ts:268-293` 的 `applyGsspHeaders` 把 `gsspRes.getHeaders()` 拷进响应头。
  - 它理论上能转发用户头，包括 `cache-control`，所以"用户头被丢"另有原因。
  - 它最后强制 `Content-Type: text/html`。
- 同文件 `:376-390` 构造 `responseHeaders`，是最可能加默认值的地方：
  - 先调 `applyGsspHeaders`。
  - 然后：有 `scriptNonce` 时用 `no-store, must-revalidate` **覆盖**；否则有 `isrRevalidateSeconds` 时设 ISR 头。
  - **gSSP 页面既无 nonce 也无 ISR 时，完全不写 Cache-Control。**
  - 无条件的 `set` 会覆盖用户头，这是潜在的坑。
- `packages/vinext/src/server/pages-page-data.ts:370-414` 的 `resolvePagesPageData` 里：
  - `:371` 的 `createGsspReqRes()` 创建 req/res。
  - `:383` 在 `res.headersSent` 时直接返回 `responsePromise`。
  - `:413` 才把 `gsspRes = res` 传出。
  - 也就是说，是否有 gSSP 在这里决定，`render` 结果里只有 `gsspRes` 非 null 才表示该页有 gSSP。
- `packages/vinext/src/server/pages-node-compat.ts:109-245` 的 `createPagesReqRes` 提供 `setHeader`（`:161`，key 转小写）、`getHeaders`（`:235`）和 `end`（`:181`）。
- `packages/vinext/src/entries/pages-server-entry.ts:637` 注入 `createGsspReqRes`。
  - `:684` 取出 `gsspRes`。
  - `:712-722` 是 `_next/data` JSON 分支。
  - `:736-773` 调 `__renderPagesPageResponse`，这是生产和 worker 入口。
- `packages/vinext/src/server/cache-control.ts:1` 已有常量 `NEVER_CACHE_CONTROL`，值正是题面要的默认字符串，可直接复用。
- `packages/vinext/src/server/dev-server.ts:501-583` 捕获 gSSP 新设置的头到 `gsspExtraHeaders`。
  - `:1055-1068` 合并到响应头：ISR 头会覆盖用户头，同样没有 gSSP 默认值。

**【3 并列与牵连】**
- 并列实现：dev server（`dev-server.ts`）和生产/worker 的入口（`pages-server-entry.ts` 加 `pages-page-response.ts`）是两套独立路径。
  - 改一处不会自动改另一处。
  - 题面说 "deploy mode"，核心是后者。
  - 为一致性，dev 路径也可能要同步。
- `_next/data` 分支 `pages-server-entry.ts:714-720` 读的是 `gsspRes.headers`，而 `res` 对象只暴露 `getHeaders()`，没看到 `headers` 属性。
  - 这看起来会让数据请求丢掉所有 gSSP 头，包括用户 `Cache-Control`。
  - 这是同类缺陷，需要同样处理。我只读了 `createPagesReqRes`，没完整确认 `PagesReqResResponse` 类型里有没有 `headers`。
- 同样走 `buildPagesCacheResponse` 的 getStaticProps 缓存命中路径（`pages-page-data.ts:222-254`）已有自己的头，不受影响。
- 其他提前返回的 gSSP 响应（redirect、notFound，`:394-411`）没有设置 Cache-Control。
  - 若题面隐含"所有 gSSP 响应"，这里也会受牵连。
- `getStaticProps` 页面的 ISR 头、nonce 头与新默认值会互相影响。
- 参考实现：Next.js 的 `getServerSideProps` 默认 `private, no-cache, no-store, max-age=0, must-revalidate`。

**【4 现有测试与约定】**
- `tests/pages-page-response.test.ts`：
  - `:78`、`:110`、`:148` 构造 `gsspRes`（null 或对象）。
  - `:178`：`expect(response.headers.get("cache-control")).toBe("s-maxage=60, stale-while-revalidate=240")`，是 ISR 用例。
  - `:334`：`.toBe("no-store, must-revalidate")`，是 nonce 用例。
- `tests/pages-router.test.ts:401`、`:3310`：同样断言 nonce 下的 `"no-store, must-revalidate"`。
- `tests/pages-page-data.test.ts` 有 8 处 gSSP 相关出现，未逐条读。
- 约定：
  - `tests/app-route-handler-response.test.ts:344` 已经用 `"private, no-cache, no-store, max-age=0, must-revalidate"`。
  - `tests/e2e/app-router/isr.spec.ts:186` 的注释也提到它，所以字符串有先例，应通过 `NEVER_CACHE_CONTROL` 复用。
- 与题面的冲突：
  - 现有 nonce 测试期望 `no-store, must-revalidate`，对 gSSP + nonce 页面是否应改为 `private, no-cache…` 并不明确。
  - 隐藏测试很可能保持 nonce 行为不变，也可能不保持。
  - 这里存在不确定性。

**【5 边界与隐含要求】**
- "用户显式设置" 的判断：
  - `res.setHeader` 的 key 被小写化，可用 `getHeaders()["cache-control"]` 判断。
  - 大小写变体 `Cache-Control` 都要被识别。
- 优先级顺序要明确：用户值 > 默认值；ISR（getStaticProps）头不应被 gSSP 默认值覆盖。
- 同时有 gSSP 和 getStaticProps 的页面，Next.js 不允许共存，影响不大。
- 默认值是否同时用于 gSSP 返回的 redirect、notFound、`_next/data` JSON 响应（Next.js 对 data 请求也带该头）。
- `res.end()` 短路（`headersSent`）的响应已由用户自己构造，不应再加默认头。
- 用户 `setHeader` 值为数组时的合并方式（`applyGsspHeaders` 用 `join(", ")`）。
- 中间件设置的 Cache-Control 与这里的优先级关系，我未查（`middleware-response-headers.ts` 有一处相关）。
- Next.js 在 dev 模式（题面为 "deploy mode"）下是否也带这个头，我没有查证。

**【6 改动规模】**
- 最小修复：1 个文件（`pages-page-response.ts`）里的 1-2 处，在 `:376-390` 补一条 gSSP 且无用户 Cache-Control 时的默认值，外加测试。
- 完整一点：再改 `pages-server-entry.ts` 的 data 分支（读 `getHeaders()`）、必要时改 `pages-page-data.ts` 的 redirect/notFound 响应、`dev-server.ts`，大约 3-4 个文件。
- 局部修补，不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
难点不在改动量，而在于判断真实缺陷的位置：`applyGsspHeaders` 看起来已经会转发用户头，题面说"用户头被丢"，所以要先弄清是 data 请求分支（`gsspRes.headers` 疑似 undefined）、nonce/ISR 覆盖，还是别处造成的，并且要处理好默认值、用户值、ISR 和 nonce 之间的优先级，不破坏现有测试。