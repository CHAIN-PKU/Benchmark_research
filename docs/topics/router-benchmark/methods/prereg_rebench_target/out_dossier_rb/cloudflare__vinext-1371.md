# 仓库档案:`<Link onNavigate>`(vinext 快照)

## 【1 题面要点】
- 要求的行为:`<Link onNavigate>` 点击时必须触发。题面称它“never fires”,并列出三个失败点:回调不触发、点击状态追踪坏了、`onNavigate` 返回值替换 history state 不生效。
- 题面没有给复现代码、期望输出和具体修法。它只给了三步建议:
  - 先在 vinext 测试里复现:“Add a test with `<Link href="/page" onNavigate={(e) => ...}>`”。
  - 研究 Next 实现:“when the callback fires, what arguments it receives, and how the return value affects navigation (e.g., preventing default, replacing history state)”。
  - 在 shim 里实现:“call `onNavigate` before performing the navigation and respect the return value”。
- 题面提到的 `.nextjs-ref/` 在快照里不存在(`ls .nextjs-ref` 报错),Next 源码和目标 e2e 用例 `test/e2e/link-on-navigate-prop/index.test.ts` 都不在仓库里。语义只能靠推断。
- 题面前提与代码不符:`onNavigate` 已有实现。题面说“不触发”,实际更可能是语义不对。隐藏测试大概率测的是具体语义,不是“有没有这个 prop”。

## 【2 相关代码】
- `packages/vinext/src/shims/link.tsx`,这是核心文件:
  - 第 62–68 行:`NavigateEvent` 类型,含 `url`、`preventDefault()`、`defaultPrevented`。
  - 第 89–90 行:prop 类型 `onNavigate?: (event: NavigateEvent) => void`,注释写“Return value is ignored”。这与题面“respect the return value”直接矛盾。
  - 第 404 行:从 props 中解构 `onNavigate`。
  - 第 538–634 行:`handleClick`,按顺序处理:
    - `onClick`;
    - `defaultPrevented` 检查;
    - `download` 属性提前返回;
    - 修饰键或非左键提前返回;
    - `target` 非 `_self` 提前返回;
    - 外部链接提前返回;
    - `e.preventDefault()`(第 567 行);
    - 第 571–576 行解析相对 href;
    - 第 579–601 行调用 `onNavigate`:构造 `navEvent`,调用 `onNavigate(navEvent)`,若 `defaultPrevented` 就 `return`。URL 解析失败被 `catch {}` 吞掉,而 `onNavigate` 本身也在这个 `try` 里,所以回调抛错也会被吞。
    - 第 605–614 行:App Router 分支,走 `React.startTransition(() => navigateClientSide(...))`。
    - 第 615–633 行:Pages Router 分支,走 `navigatePagesRouterLink`,失败则回退到 `pushState`/`replaceState`。
  - 第 664–679 行:渲染 `<a onClick>`。
  - 第 645–662 行:危险 scheme 的分支不带 `href`、不带导航处理。
- `packages/vinext/src/shims/navigation.ts:1347`:`navigateClientSide(href, mode, scroll, programmaticTransition)`,负责 App Router 的 push/replace。
- `packages/vinext/src/client/pages-router-link-navigation.ts`:`navigatePagesRouterLink`,负责 Pages Router 的 push/replace。
- `packages/vinext/src/shims/next-shims.d.ts:130`:对外类型 `onNavigate?: (event: { preventDefault(): void }) => void`,与 `link.tsx` 的类型不一致,没有 `url`。
- `packages/vinext/src/shims/url-utils.ts:175`:`toBrowserNavigationHref`,其注释写明用于 onNavigate 回调。

## 【3 并列与牵连】
- 类型有两份(`link.tsx:62-90` 和 `next-shims.d.ts:130`),语义若变要同步。
- 导航分两条路径:App Router 的 `navigateClientSide` 和 Pages Router 的 `navigatePagesRouterLink`。`onNavigate` 在两条路径之前统一调用,所以改调用时机或语义是共用的。
- 仓库里还有一个依赖现有行为的使用方:`examples/app-router-playground/app/view-transitions/_ui/transitions.tsx` 用 `onNavigate` + `preventDefault` 做 View Transitions。
- 题面提到“click state tracking”。我没找到现成的“点击状态”逻辑,没有看到相关 state 或 ref,可能要新增,也可能指 Next 测试里测试页自己的状态。这一点我不确定。
- 题面提到的“history state replacement via return value”,在现有代码里没有对应路径,`replace` prop 只在 `navigateClientSide` 的 mode 里生效。
- `useLinkStatus` 的 `pending` 状态(`setPending`)和 `startTransition` 的调用都在 `onNavigate` 之后。若把 `onNavigate` 挪进 transition,要留意这些行为。

## 【4 现有测试与约定】
- `tests/shims.test.ts:14704-14769`:这些用例是自己造一个 `navEvent` 对象再断言,并不渲染真实 Link。例如 `expect(navEvent.defaultPrevented).toBe(true)`。它们对真实点击流程基本没约束力。
- `tests/link-navigation.test.ts:505-543`:移植自 Next 的 `link-on-navigate-prop`,测的是 download 链接。断言 `expect(onNavigate).not.toHaveBeenCalled()`、`expect(startTransition).not.toHaveBeenCalled()`、`expect(navigate).not.toHaveBeenCalled()`。此处可见隐藏测试的风格:单测里 mock React 的 `startTransition`、`window` 和 navigation runtime,用 `capturedAnchorProps.onClick` 手动触发。
- `tests/e2e/pages-router/link-advanced.spec.ts:98-118` 与 `tests/e2e/app-router/nextjs-compat/navigation.spec.ts:147`:断言 `onNavigate` 报告的是解析后的 URL(如 `/link-test?page=2`)。夹具在 `tests/fixtures/pages-basic/pages/link-test.tsx:51-60` 和 `tests/fixtures/app-basic/app/nextjs-compat/nav-link-test/relative-query-link.tsx:20-26`,其中 `event as typeof event & { url: URL }`。这是要保留的既有行为。
- 外部规范是 Next 16 的 `link.tsx`,仓库里没有副本。从上面的注释看,Next 的 `NavigateEvent` 带 `url` 和 `preventDefault`;题面“respect the return value”与代码注释“Return value is ignored”冲突,我没法确认 Next 里返回值到底怎么用,这一点要靠智能体自己判断。
- `CLAUDE.md`/`AGENTS.md` 里没有搜到与 `onNavigate` 相关的约定。

## 【5 边界与隐含要求】
- 回调在哪个时机触发:现在在 `e.preventDefault()` 之后、`startTransition` 之前同步调用。若要求在 transition 内、或在 `navigateClientSide` 内部触发,需要重排。
- `onNavigate` 抛错被 `catch {}` 吞掉,可能让测试看不到错误,也可能让导航继续。
- `preventDefault` 之后不再导航,但 `pending` 状态不会被设置,这点对“click state”可能有影响。
- hash-only、相对 query 链接、`replace` prop、`scroll` prop、`basePath`、`trailingSlash`、i18n locale 前缀下传给回调的 `url` 要正确。
- 不触发的情形要保持:`download`、修饰键、非左键、`target="_blank"`、外部链接、`onClick` 已 `preventDefault`。这些已有测试保护。
- Pages Router 和 App Router 两条路径都要触发。
- 同一次点击只触发一次(没有现成的去重逻辑,但目前也没有会重复调用的路径)。
- 危险 scheme 分支不带导航处理,保持不变。

## 【6 改动规模】
- 看起来是局部修补:主要改 `link.tsx` 的 `handleClick`(约 20–40 行)。若需要追踪点击状态,可能新增一个小 state 或 ref。
- 另外同步 `next-shims.d.ts` 的类型,并补测试(单测加 e2e 夹具)。
- 大概 2–4 个文件,不需要贯穿多层,除非要把 `onNavigate` 下沉到 `navigateClientSide` 内部。

## 【7 难点一句话】
题面说“未实现”,但代码里已有实现,而且 Next 参考源码和目标 e2e 用例都不在仓库里。难点在于凭有限信息判断隐藏测试真正考的语义差异:返回值怎么用、触发时机、点击状态和 history state 怎么处理。