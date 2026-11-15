## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 可能要一并处理的位置
- `src/diff/children.js` 的 `diffChildren`（约第 50–64 行）：字符串和数字被包装成文本 vnode，bigint 目前落到后面的 vnode 分支，这是报错来源。同文件的 `toChildArray`（约第 275 行起）对 boolean 和 null 有单独判断，要核对 bigint 经过它之后的结果。
- 依赖 `toChildArray` 的调用方：`compat/src/Children.js`、`compat/src/suspense-list.js`、`compat/src/render.js`。bigint 经过这些路径时不应出错或被丢掉。
- `src/index.d.ts` 的 `ComponentChild` 类型（约第 46 行）和 `src/jsx.d.ts`：类型上是否允许 bigint 也要核对。
- `src/diff/index.js` 约第 361 行处理文本节点（`dom.data = newProps`，并和 `oldProps` 比较）：bigint 作为文本内容时要核对。

B. 可能被检查的输入与边界
- 单独的 `{5n}`，以及和字符串、数字、元素混排的 `{5n}`、`{0n}`。`0n` 是 falsy，要确认不会像 null 或 false 那样被丢弃。
- 重新渲染时 bigint 变成另一个 bigint，或变成 number、string：文本节点是否更新，`oldProps !== newProps` 在类型变化时的表现。
- 数组、Fragment 里的 bigint，以及函数组件返回 bigint。

C. 已有约定
- `diffChildren` 里的文本节点用 `createVNode(null, text, ...)` 的形式（type 为 null，props 为文本本身），bigint 要沿用同一约定。
- `test/browser/` 下已有 number、string、boolean 的渲染测试可参照；`debug/` 里对无效 vnode 的校验要确认不会拒绝 bigint。
- 仓库有 size 和 minify 约束，测试环境是否支持 bigint 字面量也要留意。

D. 提交前建议自测
1. `render(<span>{5n}</span>)` 的 DOM 文本为 "5"。
2. `0n` 能渲染出 "0"，在 `[1n, 2n]` 数组和混排情况下顺序正确。
3. 同一位置从 `1n` 重渲染为 `2n`，再换成数字或字符串，DOM 文本随之更新；再跑 debug 和 compat 现有测试确认无回归。
