# 仓库档案：useErrorBoundary 导致列表项重复渲染

以下内容均来自对快照代码的阅读，未参考上游修法。我没有运行复现，所以"旧 DOM 残留"是根据代码推断出的机制。

## 【1 题面要点】
- 要求的行为：已挂载的列表项 `TodoItem` 在更新时，子组件 `TodoItemInner` 抛错，被 `TodoItem` 自己的 `useErrorBoundary` 捕获。此时该项应只渲染错误态 `<li>An error occurred…</li>`，和初次渲染就出错的 "Write my first post" 项一致。
- 实际行为：错误态 `<li>` 和原来的正常 `<li>` 同时存在，即重复渲染。
- 题面给了完整复现代码，操作是勾选 "Buy new groceries"。期望输出只有一句：`The item should have rendered the same way as the "Write my first post" item.`
- 没有修法建议，也没有指向具体代码。
- 复现用到的是 signals，但机制应与 signals 无关：任何"已挂载的子组件在更新中抛错"的场景都会触发。

## 【2 相关代码】
- `src/diff/index.js:255-276`：组件 diff 的 `catch (e)` 块。
  - 先设 `newVNode._original = null`，再调 `options._catchError(e, newVNode, oldVNode)`。
  - 抛错的新 vnode 没有 `_dom`，`_children` 也只是半成品或为空。
  - 水合和初次创建的分支会保留 `_dom = oldDom`，更新路径则没有这一步。
- `src/diff/catch-error.js:10-43`：`_catchError` 沿 `_parent` 向上找最近的边界。
  - 靠 `getDerivedStateFromError` 或 `componentDidCatch` 加 `component._dirty` 判断是否已处理。
  - 处理后设 `_pendingError`。
- `hooks/src/index.js:376-393`：`useErrorBoundary`。
  - 给组件挂 `componentDidCatch`，里面调 `errState[1](err)` 触发重渲染。
- `src/diff/children.js:128-143`：匹配到的旧 vnode 先被置 `oldChildren[matchingIndex] = undefined`，再进入 `diff`。
  - 一旦 diff 抛错，这个旧 vnode 就不会进入 `children.js:~224` 的"移除剩余旧子节点"循环。
- `src/diff/children.js:185`：`isMounting = oldVNode === EMPTY_OBJ || oldVNode._original === null`。
- `src/diff/index.js:517-565`：`unmount`。
  - 它只会 `removeNode(vnode._dom)` 和递归 `_children`，而失败的 vnode 这两项都是空的。
- `compat/src/suspense.js:5-23`：参考实现。
  - Promise 抛出时，它会在 `_catchError` 钩子里补上 `newVNode._dom = oldVNode._dom; newVNode._children = oldVNode._children`。

推断的机制：
1. 更新时子 vnode 抛错，旧 vnode 已脱离 `oldChildren`，新 vnode 又没有 `_dom` 或 `_children`。
2. 边界重渲染出错误态 `<li>` 时，没有任何 vnode 持有旧的正常 `<li>`，它既没被卸载，也没被复用。
3. 旧 `<li>` 因此残留在 DOM 里，与错误态并存。

## 【3 并列与牵连】
- 并列实现：Suspense 钩子已经做了"抛错后从旧 vnode 继承 `_dom/_children`"，错误边界路径没有。修复很可能是把同样的处理放到通用的 `catch` 块或 `_catchError` 中，而不是只改 hooks。
- 其他 `_catchError` 调用点：
  - `src/diff/index.js:324`：commitRoot 里的回调抛错。
  - `src/diff/index.js:511`：`applyRef`。
  - `src/diff/index.js:537`：`componentWillUnmount`。
  - `hooks/src/index.js:94,115,424`：hooks 的 effect 错误。
  - 这些调用点的 vnode 语义不同，通常没有 `oldVNode` 参数，改动时要避免影响它们。
- 类组件的 `componentDidCatch` 和 `getDerivedStateFromError` 边界走同一路径，所以这不是 hooks 专属的 bug。
- 会影响到的行为：水合路径（`isHydrating` 分支）、Suspense 的 `oldVNode` 回退、`_pendingError` 和 `_processingException` 的重渲染流程。

## 【4 现有测试与约定】
- 相关测试文件：
  - `hooks/test/browser/errorBoundary.test.js`（`useErrorBoundary`，如 `'catches errors'` 在第 20-45 行）。
  - `test/browser/lifecycles/componentDidCatch.test.js`（如 `'should re-render with new content'`，第 446 行；`'should be called when child fails in render'`，第 144 行）。
  - `test/browser/lifecycles/getDerivedStateFromError.test.js`。
  - `compat/test/browser/componentDidCatch.test.js`。
- 现有测试的断言以 `scratch.innerHTML` 等于错误态为主，例如 `expect(scratch.innerHTML).to.equal('<p>Error</p>')`。
- 这些测试大多是"初次挂载即抛错"，我没看到"已挂载后更新时抛错"的用例，这正是本 bug 的缺口。隐藏测试大概率就是补这一类，用 `scratch.innerHTML` 断言错误态里没有残留旧 DOM。
- 没有外部规范，行为由现有测试和 Suspense 的做法定义。与题面期望不冲突。

## 【5 边界与隐含要求】
- 旧子树必须被卸载，而不是只被隐藏：`componentWillUnmount`、ref 清理、effect 清理都要跑，不能漏。
- 兄弟节点顺序：错误态 `<li>` 要落在原位置，不能被挤到末尾。
- 键控列表和无 key 列表（题面用 `key={index}`）都要正确，同一父节点下多个项各自出错也不能互相影响。
- 错误被边界处理之后，恢复（`reset`）和再次更新仍要正常。
- 抛出 Promise 的 Suspense 路径不能被破坏。
- 没有边界、错误一路向上抛到根的场景不能被改坏。
- 错误发生在 Fragment 或嵌套函数组件之下时，`_dom` 要从正确的层级继承。
- 水合时抛错的既有逻辑要保持不变。

## 【6 改动规模】
- 预计改 1-2 个核心文件，每处几行：`src/diff/index.js` 的 `catch` 块，或 `src/diff/catch-error.js`，也可能涉及 `src/diff/children.js`。
- 属于局部修补，不需要新增结构，也不需要贯穿多层。
- 还需要补测试，位置在 `hooks/test/browser/errorBoundary.test.js` 或 `test/browser/lifecycles/componentDidCatch.test.js`。

## 【7 难点一句话】
代码改动本身很小，难点在于定位：要看出症结是"更新中抛错的 vnode 丢掉了对旧 DOM 和旧 children 的引用，导致没人卸载旧节点"，并且要放在对其他 `_catchError` 调用点、水合和 Suspense 都安全的位置。