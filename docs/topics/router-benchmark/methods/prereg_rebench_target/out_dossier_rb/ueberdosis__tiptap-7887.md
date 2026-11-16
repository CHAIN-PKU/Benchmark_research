我在整理档案，已查完核心代码，下面直接输出。

# 仓库档案：unsetAllMarks 与 `clearable`

## 【1 题面要点】
- 要求：`unsetAllMarks` 默认只清除"可清除"的 mark。comment 这类语义 mark 要能保留，不被清除格式按钮删掉。
- 复现：只有文字描述，没有代码。用户的临时办法是对每个格式 mark 逐个调用 `unsetMark`。
- 期望输出："`unsetAllMarks` will remove formatting marks … but not remove comment tags or comments."
- 修法建议在 "Evaluation contract" 和 "Interface" 里，相当明确：
  - 新增 `MarkConfig.clearable: boolean | (() => boolean)`，默认 `true`。
  - "A mark configured with `clearable: false` must survive `unsetAllMarks()`, while `unsetAllMarks({ignoreClearable: true})` removes it."
  - "`can().unsetAllMarks()` on a selection containing only non-clearable marks is a successful no-op and must return `true`".
  - "explicitly calling `unsetMark` may still remove a non-clearable mark."
- comment 扩展本身是 PRO 包，不在这个仓库里。测试只能自定义一个 `clearable:false` 的 Mark。

## 【2 相关代码】
- `packages/core/src/commands/unsetAllMarks.ts:15-32`：当前实现。
  - 第 21 行：`empty` 时直接返回 `true`。
  - 第 25-29 行：`dispatch` 存在时，对每个 range 调用 `tr.removeMark(from, to)`，没有传 mark 类型，所以会清掉所有 mark。
  - 第 10 行：类型声明是 `unsetAllMarks: () => ReturnType`，需要改成接受 `options?: { ignoreClearable?: boolean }`。
- `packages/core/src/Mark.ts:8-62`：`MarkConfig` 接口。
  - `keepOnSplit`（第 31 行）和 `exitable`（第 62 行）都是 `boolean | (() => boolean)`，`clearable` 应仿照它们的写法。
  - 这里还要加 JSDoc。
- `packages/core/src/ExtensionManager.ts:451-467`：`setupExtensions` 里用 `callOrReturn(getExtensionField(extension,'keepOnSplit',context)) ?? true` 解析 mark 的布尔配置，结果放进 `splittableMarks`。
- `ExtensionManager.ts:129-134`：`exitable` 的读取方式。
- `packages/core/src/commands/unsetMark.ts:33-65`：单个 mark 的移除。它不检查 `clearable`，契约也要求保持这样。

## 【3 并列与牵连】
- `unsetAllMarks` 只有一份实现，没有并列版本。
- `ExtensionManager` 里有两处已有的 mark 布尔字段解析（`splittableMarks`、`exitable`），`clearable` 可以照抄它们的模式，不是必须新增结构。
- `unsetAllMarks` 的调用点都在 `demos/` 里，约 15 处，都是不带参数的调用。新增的可选参数向后兼容，demo 不用改。
- `unsetAllMarks` 常与 `clearNodes` 链式使用（`demos/src/Examples/CollaborativeEditing/*/MenuBar.*`）。
- `can().unsetAllMarks()` 在 demo 里用于控制按钮是否可点（如 `Default/React/menuBarState.ts:19`）。
- `unsetAllMarks` 默认行为改了之后，任何 `clearable:false` 的扩展都会受影响，目前仓库内没有这样的扩展。
- 我没找到任何 .md/.mdx 文档提到 `unsetAllMarks` 或 `clearable`，所以仓库里没有需要同步的文档。

## 【4 现有测试与约定】
- 没有任何现有测试覆盖 `unsetAllMarks`。`packages/core/__tests__/delete.spec.ts:57` 只有 `expect(() => editor.commands.unsetMark('bold')).not.toThrow()`。
- `packages/core/__tests__/can.spec.ts` 展示了 `can()` 的断言写法，例如 `editor.can().setMark('bold')` 和 `editor.can().chain().undo().run()`。
- `CommandManager.ts:108-113` 和 `:135`：`can()` 用 `dispatch = false`（或 `undefined`）构造 props，命令要在 `dispatch` 为空时也返回 `true`。
- 现有实现的约定是：空选区返回 `true`；非空选区总是返回 `true`；即使没有 mark 可清除也不返回 `false`。题面的 "successful no-op must return true" 与这个约定一致，不冲突。
- 仓库里没有外部规范决定行为，行为由题面契约决定。

## 【5 边界与隐含要求】
- `clearable` 既可能是 boolean，也可能是函数，要用 `callOrReturn` 解析，并且函数要带正确的 `this` 上下文（`name/options/storage/editor/type`，参考 `ExtensionManager` 里的 `context`）。
- 默认值是 `true`，所以 `undefined` 要按 `true` 处理（`?? true`）。
- 要决定怎么拿到"非 clearable 的 mark 类型集合"：
  - 用 `editor.extensionManager.extensions` 过滤出 `type==='mark'` 的扩展，再取 `clearable === false` 的；
  - 或者在 `ExtensionManager` 里预先算好一个列表；
  - 也可以在 `schema.marks` 上遍历。
  - 命令回调里要拿 `editor`，核心命令的 props 里有 `editor`，需要核实。
- 选择性移除：`tr.removeMark(from, to)` 不带类型会全部清掉。要改成遍历 `schema.marks`，对 clearable 的类型逐个 `removeMark(from, to, type)`；或者遍历范围内文本节点的 marks，只移除 clearable 的那些。
- `ignoreClearable: true` 时要回到清除全部。
- 多个选区 range（`ranges.forEach`）要都处理。
- `unsetMark` 的行为必须保持不变。
- 空选区的 stored marks：当前实现对空选区什么都不做，不要为此引入新行为。
- 被扩展覆盖或继承时，`clearable` 要能通过 `extend`/`configure` 生效。需要确认 `getExtensionField` 能处理 `parent` 继承。
- 类型声明：`unsetAllMarks: (options?: { ignoreClearable?: boolean }) => ReturnType`。

## 【6 改动规模】
- 必改：2 个文件，各几处。
  - `Mark.ts`：新增一个配置字段加 JSDoc。
  - `unsetAllMarks.ts`：改签名、改 `removeMark` 逻辑。
- 可能要改：`ExtensionManager.ts`，用于暴露 clearable 判断。如果命令里直接读扩展配置，这个文件就不用改。
- 可选：加测试、加 changeset。
- 总体是局部修补，没有贯穿多层。

## 【7 难点一句话】
难点不在改动量，而在命令里怎么可靠地拿到各 mark 的 `clearable` 配置（函数形式要带正确的 `this` 上下文，默认值要为 `true`），再把"无差别 `removeMark`"改成"按类型选择性移除"，同时守住 `can()` 和 `dispatch` 为空时返回 `true` 的契约。

**说明**：我没有核实命令 props 里是否有 `editor`，也没有核实 `getExtensionField` 对 `parent` 继承的处理。这两点需要实现时确认。