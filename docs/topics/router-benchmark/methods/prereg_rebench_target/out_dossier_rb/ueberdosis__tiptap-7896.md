**档案:extension-table 的 TableView 忽略 HTMLAttributes**

**【1 题面要点】**
- 期望行为:`Table.configure({ HTMLAttributes: { class: 'my-custom-table' } })` 在 `resizable: false`(默认)时,`<table>` 也要带上 `class="my-custom-table"`。
- 复现:用 `StarterKit`、`Table.configure({HTMLAttributes:{class:'my-custom-table'}})`、`TableRow`、`TableHeader`、`TableCell`,内容是 `<table><tbody><tr><td>cell</td></tr></tbody></table>`。查看 DOM,`<table>` 上没有这个 class。
- 修法建议原文:“A minimal fix would have `TableView` apply `this.options.HTMLAttributes` to the inner `<table>` element in its constructor.”
- 根因:3.23 新增的 `addNodeView()` 让 NodeView 取代了 `renderHTML`,而 `TableView` 从不读取 HTMLAttributes。
- 临时绕过:`View: null`。
- Interface 一节写明“No new interfaces are introduced”。
- 题面里的“`this.options`”其实在 `TableView` 里不存在。`TableView` 是独立的类,没有 options。

**【2 相关代码】**
- `packages/extension-table/src/table/TableView.ts:77-105`:`TableView` 的构造函数 `(node, cellMinWidth)`。
  - 它手工创建 `div.tableWrapper > table > colgroup + tbody`。
  - 第 98-100 行只应用 `node.attrs.style`。
  - 第 107 行起的 `update(node)` 只调用 `updateColumns`。
- `packages/extension-table/src/table/table.ts:523-535`:`addNodeView()`。
  - 非 resizable 且 `View` 非空时,返回 `({node, view}) => new View(node, this.options.cellMinWidth, view)`。
  - 这里可以拿到 `this.options.HTMLAttributes`,但目前没有传给 View。
- `table.ts:88`:`View` 选项的类型是 `new (node, cellMinWidth, view: EditorView) => NodeView`。
- `table.ts:286-309`:`renderHTML` 的行为是参照标准。
  - 它调用 `mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, {style: getTableStyle()})`。
  - 当 `renderWrapper` 为 true 时,外面再包一层 `div.tableWrapper`。
- `table.ts:502-521`:resizable 且可编辑时,`columnResizing({..., View: this.options.View})` 也会实例化同一个 View。

**【3 并列与牵连】**
- 有两条路径会构造 `TableView`:
  1. `addNodeView`(非 resizable)。
  2. `columnResizing` 插件(resizable)。
  - 它在插件里的构造签名由 prosemirror-tables 决定,大概率只传 `(node, cellMinWidth)`,不会传 HTMLAttributes。我没有读那个依赖的源码来确认。
  - 这与 issue 里关联的 #6176(resizable:true 同样症状)吻合。只改 `addNodeView` 这条路径,resizable 的情况不会好。
- 三个调用点(`new View(...)`、`columnResizing`、`renderHTML`)共用同一个 `View` 类型。
- 签名变化会影响自定义 `View` 的使用者。仓库里没有其他 `new TableView` 的调用点,`src/index.ts:6` 把 `TableView` 导出为公共 API。
- `renderHTML` 的合并还包含节点自身的 HTMLAttributes(`node.attrs` 渲染结果),不只是 options 里的 HTMLAttributes。
- `update()` 的复用逻辑也受影响。

**【4 现有测试与约定】**
- `__tests__/colgroupUpdate.spec.ts:55` 的 `describe('resizable: false (default — bug case)')` 里断言列删除后的 `colgroup > col` 数量,例如 `expect(countCols(editor)).toBe(2)`。
- 没有任何测试断言 HTMLAttributes 或 `class`。`tableCell`、`tableHeader`、`tableCommands`、`tableMarkdown` 的 spec 里也没有 `TableView` 或 `HTMLAttributes` 的匹配。
- 测试样板:创建 `Editor`,`Table.configure({resizable})`,通过 `editor.view.dom.querySelector` 查询 DOM。隐藏测试很可能是同样的写法,检查 `table.classList.contains(...)`。
- 约定:`renderHTML` 是规范来源(`table.ts:301`)。
- `.changeset/` 目录里有 md 文件,例如 `2026-05-29-placeholder-empty-node-class-function.md`,仓库要求补 changeset。
- 与题面不冲突。

**【5 边界与隐含要求】**
- 合并语义要和 `renderHTML` 保持一致:`HTMLAttributes` 与 `node.attrs.style` 同时存在时,style 的优先级要处理好。
  - 现在 `style` 通过 `cssText` 设置,再由 `updateColumns` 改 width/min-width。
  - 如果 HTMLAttributes 里自带 `style`,需要决定是合并还是被覆盖,避免把 `updateColumns` 的结果冲掉。
- 如果用户设了 `class`,但 wrapper div 的 `tableWrapper` class 不能被覆盖。
- 属性应该落在内层 `<table>`,不是 wrapper。
- 需要选择:通过构造函数新增第三/四个参数(向后兼容,可选参数),还是改用 options 对象。
- `update(node)` 时 HTMLAttributes 是静态 options,不需要重新应用;但如果节点上有自己的 attrs,可能要同步。
- `renderWrapper` 选项对 NodeView 无效:NodeView 总是带 wrapper。这是已有行为,不在本题范围。
- `View: null` 的绕过方式要继续可用。
- resizable 路径是否也要修,题面没说。
- 自定义 `View` 的类型签名变化要保持兼容(参数可选)。

**【6 改动规模】**
- 最小改动:2 个源文件,3-5 处。
  - `TableView.ts` 构造函数新增参数并应用属性。
  - `table.ts:534` 传入 `this.options.HTMLAttributes`。
  - 可选:`table.ts:88` 的类型。
- 外加 1 个 changeset 和 1 个测试。
- 局部修补,不涉及新结构。
- 要覆盖 resizable 路径,可能还要改 `columnResizing` 的调用方式,例如包一层子类或闭包,规模会略大。

**【7 难点一句话】**
难点不在补一行 `setAttribute`,而在 `TableView` 拿不到 `options`,必须设计参数传递,并且要和 `renderHTML` 的合并、style 优先级、resizable 路径(由 prosemirror-tables 实例化)保持一致。