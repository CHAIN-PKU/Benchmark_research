**档案：Preact hooks 的 effect cleanup 抛异常导致卸载中断**

**【1 题面要点】**
- 要求的行为：effect 的 cleanup 函数抛异常时，组件仍要完整卸载。后面的 cleanup 要继续执行，DOM 不能残留，错误要交给 ErrorBoundary，和 React 一致。
- 复现：`MainContent` 有两个 `useEffect`。第一个依赖 `[val]`，cleanup 里 `throw new Error("oops")`，并在 `setTimeout` 里切换 val。第二个依赖 `[]`，cleanup 里 `console.log("MainContent unmount")`。外层是用 `componentDidCatch` + `setState` 的 ErrorBoundary。
- 期望输出：先打印 `Error: oops`，然后打印 `MainContent unmount`，DOM 里只剩 `<h2>`。
- 实际现象：`<h1>` 和 `<h2>` 同时存在，第二个 cleanup 没被调用。
- 题面没有给修法建议。

**【2 相关代码】**
- `hooks/src/index.js:29-41`，`options._render`。重渲染时先执行 `hooks._pendingEffects.forEach(invokeCleanup)`，这一步没有 try/catch。题面场景里，第一个 effect 的 cleanup 就在这里抛出，被 `src/diff/index.js:245` 的 catch 捕获，再调用 `_catchError`。
- `hooks/src/index.js:72-83`，`options.unmount`。它执行 `c.__hooks._list.forEach(invokeCleanup)`，整体包在一个 try/catch 里。第一个 cleanup 一抛，forEach 就中断，后面的 hook 都不会清理。
- `hooks/src/index.js:345-351`，`invokeCleanup`。它只做 `hook._cleanup()`，调用前不清空 `_cleanup`。抛异常后 `_cleanup` 还留着，卸载时同一个 cleanup 会再被调用一次，再抛一次。
- `hooks/src/index.js:53-70`，`options._commit`。这里对 `_renderCallbacks` 的 `invokeCleanup` 同样有风险，但有 try/catch。
- `hooks/src/index.js:286-300`，`flushAfterPaintEffects`。这里的 cleanup 和 effect 都在一个 try 里，出错后只是清空 `_pendingEffects`。
- `src/diff/index.js:478-505`，`unmount`。先调 `options.unmount(vnode)`，再 `componentWillUnmount`，然后递归卸载子节点和移除 DOM。
- `src/diff/catch-error.js:8-38`，`_catchError`。沿 `_parent` 向上找边界。找不到就重新 throw。

**【3 并列与牵连】**
- `invokeCleanup` 有四个调用点：`_render`(37)、`_commit`(56)、`unmount`(78)、`flushAfterPaintEffects`(290)。
- `invokeEffect`（357）是成对函数，effect 本身抛异常的情况同理。
- `compat/src/suspense.js:48` 有一处单独调用 `effect._cleanup()`，处理 suspense 卸载时的 effect，也没有保护。
- `options.unmount` 和 `src/diff/index.js` 的 `unmount` 是成对的。上游 `_catchError` 的错误处理会影响 `componentWillUnmount` 一路。
- 这里改动会影响所有 hooks 组件的卸载和重渲染路径。

**【4 现有测试与约定】**
- `hooks/test/browser/errorBoundary.test.js` 只测 `useErrorBoundary`，例如 `expect(scratch.innerHTML).to.equal('<p>Error</p>')`（36、58、80 行）。其中没有测 cleanup 抛异常的用例。
- 这次没有细读 `hooks/test/browser/useEffect.test.js`，但这里大概率是新增测试的落点。
- 约定来自 React：cleanup 抛错后，其余 cleanup 仍要执行，DOM 要清除。
- 与题面期望没有冲突。

**【5 边界与隐含要求】**
- 多个 cleanup 都抛异常时，要决定处理哪一个错误，以及能否全部上报。
- 同一个 cleanup 不能被调用两次，所以抛错前要先清空 `_cleanup`。
- `invokeCleanup` 里 `currentComponent` 的还原：抛错时 `currentComponent = comp` 没执行，需要用 try/finally。
- 错误边界处于 `_processingException` 时，要避免死循环或错误被吞掉。
- 卸载路径里抛出的错误，要上报给边界，卸载本身不能停。
- 同时要考虑 `_render` 路径：重渲染中抛错时，要保证重试或卸载流程不重复清理。
- 不带边界时，错误最终仍应重新抛出。

**【6 改动规模】**
- 主要改 `hooks/src/index.js` 一个文件，约 2~4 处：`invokeCleanup`、`options.unmount`、`_render`，可能还有 `flushAfterPaintEffects`。
- 局部修补，不需要新增结构。
- 可能附带改 `compat/src/suspense.js` 和测试。

**【7 难点一句话】**
难在要弄清异常有两条路径：重渲染时的 `_render` 和卸载时的 `options.unmount`。还要保证抛错的 cleanup 只执行一次、后续 cleanup 照常执行、错误仍能交给 ErrorBoundary。