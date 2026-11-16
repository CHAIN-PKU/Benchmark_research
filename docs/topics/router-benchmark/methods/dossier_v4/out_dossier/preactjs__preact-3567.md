# 仓库档案：preact #3567（hooks 里 render 期间 setState 导致 `useEffect(fn, [])` 的 cleanup 被误触发）

## 【1 题面要点】
- 要求的行为：`useEffect(..., [])` 的 cleanup 只能在组件卸载时执行。组件在 render 期间调用 `setA(false)`，点击时 state 从 true 变回 false，这种情况下 cleanup 不应该执行。
- 复现：issue 给了一段 `Foo` 组件。它有 `useState(false)`，`useEffect(() => () => alert(...), [])`，render 里直接 `setA(false)`，按钮的 onClick 调用 `setA(true)`。点击按钮后 alert 弹出。
- 期望：alert 永远不触发。
- 回归范围：10.7.3 正常，10.8.0 开始出问题。
- 修法建议：题面没有给。只说了“新的 state-settling 逻辑”有问题。

## 【2 相关代码】
- `hooks/src/index.js:32-53`：`options._render` 钩子，是根因。
  - 当 `previousComponent === currentComponent`，说明同一组件在 render 循环里被连续 render（见下方 `src/diff/index.js`）。
  - 此时它执行 `hooks._pendingEffects = []`，`_renderCallbacks = []`，并对 `hooks._list` 里所有 hook 执行 `if (hookItem._args) hookItem._args = undefined`（43-45 行）。
  - 这是对**所有** hook 无差别清空 `_args`，包括上一轮根本没有排入 pending 的 effect。
- `hooks/src/index.js:173-182`（`useEffect`）和 `188-197`（`useLayoutEffect`）：用 `argsChanged(state._args, args)` 决定是否重新排入。`_args` 被清成 `undefined` 后，`argsChanged` 在 394-400 行恒返回 true（`!oldArgs`）。于是第二遍 render 把 `[]` 的 effect 当成新的重新 push。
- `hooks/src/index.js:47-48`、`313-315`：执行下一轮 effect 前先 `invokeCleanup`，因此旧 cleanup 被调用，就是 alert。
- `hooks/src/index.js:229-239`（`useMemo`）：同样依赖 `_args`，被清空会导致 memo 重算。
- `src/diff/index.js:186-194`：函数组件的 `do { c._dirty=false; renderHook(newVNode); render } while (c._dirty && ++count < 25)`。这是 10.8.0 新增的 render 内 setState 循环，触发源头。
- `src/diff/index.js:230-232` 附近：`_renderCallbacks` 入队 commitQueue。

## 【3 并列与牵连】
- `useEffect` 与 `useLayoutEffect` 是并列实现。layout effect 走 `_renderCallbacks`（195 行），其 `_args` 同样会被误清，所以修复必须对两者都生效。
- `useMemo`（含 `useCallback`、`useRef`，它们都基于 `useMemo`）也依赖 `_args`。清空 `_args` 会让 memo 在循环第二遍重新计算。`useRef` 用 `useMemo(..., [])`，被清空后 `ref.current` 会重置，这很可能是更严重的牵连 bug。
- `useImperativeHandle` 基于 `useLayoutEffect`。
- 其他调用点：`options.diffed` 里把 `previousComponent` 置 null（62-64 行），`options._diff` 里把 `currentComponent` 置 null（27-30 行）。
- `compat` 里的 `useSyncExternalStore` 与 `useTransition` 若依赖 hooks，可能间接受影响（未深查）。

## 【4 现有测试与约定】
- `hooks/test/browser/useState.test.js:215-235`：`'should render a second time when the render function updates state'`，断言 `expect(calls).to.deep.equal(['bye','hi'])`。这条测试要继续通过，因此循环 render 必须保留。
- 目前没有测试覆盖“render 内 setState 且已挂载的 `[]` effect 不应触发 cleanup”。隐藏测试大概率是在 `useEffect.test.js` 或 `useState.test.js` 里新增这类用例，断言 cleanup 未被调用，或 effect 只执行一次。
- 外部规范：React 的语义是 render 阶段 setState 只重跑 render，不重跑 effect。已执行过的 `[]` effect 不应重新排入。
- 约定：清空 `_args` 的原意是，循环第一遍里“排入但未执行”的 effect，在重新 render 后需要重新排入。这与题面期望并不冲突，只是清空的范围过宽。

## 【5 边界与隐含要求】
- 首次挂载时在 render 里 setState：第一遍排入的 effect 已被丢弃（`_pendingEffects` 重置），第二遍必须重新排入，否则 effect 永远不会跑。这个场景必须保留。
- 更新时：未变化的 effect（如 `[]`）第二遍不应重复排入。依赖变化的 effect 只应排入一次，不能重复执行。
- 已执行过的 effect 的 `_args` 和 `_cleanup` 要保持原值。只有“本轮第一遍才修改了 `_args` 和 `_value`”的 hook，才需要回滚到之前的 `_args`。
- layout effect 的 `_renderCallbacks` 同理。`componentDidMount` 和 `componentDidUpdate` 也在 `_renderCallbacks` 里，被整体清空是否安全需要留意。
- useMemo 在循环中不应丢失已有值。
- 循环上限 25 次。多次循环、setState 多次的情况也要处理。

## 【6 改动规模】
- 约 1 个文件（`hooks/src/index.js`），改动集中在 `options._render` 的 43-45 行附近，局部修补。
- 如果选择“只回滚本轮排入的 hook 的 `_args`”，需要在 `useEffect` 和 `useLayoutEffect` 里多记录旧值，可能触及 `internal.d.ts` 和 `mangle.json`，属于小幅新增结构。
- 另需新增 1 个测试。

## 【7 难点一句话】
难在 `_args` 的清空必须从“全部 hook”收窄到“上一遍中确实被排入但未执行的 effect”（并区分 useMemo），同时保证首次挂载时循环 render 里的 effect 仍会重新排入。