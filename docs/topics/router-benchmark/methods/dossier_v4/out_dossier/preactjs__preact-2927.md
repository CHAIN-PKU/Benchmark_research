【1 题面要点】
- 期望行为：`<p contentEditable={undefined}>` 不应抛错，与 React 一致。
- 实际报错：`Failed to set the 'contentEditable' property on 'HTMLElement': The value provided ('') is not one of 'true', 'false', 'plaintext-only', or 'inherit'`。
- 题面只给了两个 codesandbox 链接，没有可粘贴的最小复现，没有期望输出，也没有给修法建议。
- 题面没说明 `null` 要不要同样处理，也没说 `false` 怎么处理。

【2 相关代码】
- `src/diff/props.js:56-150` 的 `setProperty` 是主要修改点。
- `props.js:106-119`：属性名满足 `name in dom` 且不在排除列表（`list/tagName/form/type/size/download/href`）时，走属性赋值分支。该分支是 `dom[name] = value == null ? '' : value;`（119 行）。`contentEditable` 在 `HTMLElement` 上存在，所以会执行 `dom.contentEditable = ''`，浏览器因此抛错。
- 排除列表的注释写着“只读但可用 setAttribute 设置”。`download` 和 `href` 也在这个列表里，处理方式是走 `setAttribute` / `removeAttribute`。
- `props.js:134-148`：`value == null` 时调用 `removeAttribute(name)`。`contentEditable` 要走这条路径时，`removeAttribute('contentEditable')` 在 HTML 文档里不区分大小写，可以删掉 `contenteditable` 属性。
- `props.js:13-34` 的 `diffProps`：移除 prop 时调用 `setProperty(dom, i, null, ...)`（18 行），更新时用 `oldProps[i] !== newProps[i]` 判断（29 行）。`undefined` 和 `null` 都会进入 `setProperty`。

【3 并列与牵连】
- 同类问题：凡是在 DOM 上存在、但不接受 `''` 的枚举型属性，都会有同样的崩溃。例如 `draggable`、`spellcheck` 的赋值行为需要留意。题面只要求 `contentEditable`。
- `src/diff/index.js:428,435` 另外调用 `setProperty` 处理 `value` 和 `checked`，不涉及 `contentEditable`。
- 对 `setProperty` 做通用改动（例如在 119 行之前先判断 `value == null`）会影响所有走赋值分支的属性，并改变清除时置 `''` 的现有行为，比如 `value`、`className`、`id`、`title`。
- 在排除列表里加 `contentEditable` 是局部改动。代价是 `contentEditable={true}` 会变成 `setAttribute('contentEditable', true)`，即 `contenteditable="true"`，需要确认这符合预期。
- `test/fixtures/preact.js` 是旧版本的构建产物（124 行有 `'spellcheck' != name` 的特殊处理），不需要改。
- `compat` 和 `hooks` 目录里没有找到对 `setProperty` 的调用。

【4 现有测试与约定】
- 没有现有测试专门针对 `contentEditable={undefined}`。
- `test/browser/render.test.js:815-855` 的测试用 `contentEditable`（值为 true）验证 `innerHTML` 的 diff，并通过 `querySelector('[contenteditable]')` 查询。如果改成 `setAttribute`，这个选择器仍然能匹配。
- `render.test.js:384-387`：`render(<input spellcheck={false} />)` 之后断言 `.spellcheck === false`，说明布尔值要走属性赋值。
- `render.test.js:389-395`：`download={null}` 之后断言 `getAttribute('download')` 为 `null`，这个断言已覆盖“`null` 时移除属性”的约定，可作为参考。
- `render.test.js:476` 起的 `should unset href if null || undefined` 是同类写法，新测试可以照着写。
- `render.test.js:1055-1069` 的测试在 `className` 为 `undefined` 时断言属性被移除。
- 仓库内没有找到外部规范文件，参考实现是 React 的行为：`undefined` 时不设置属性。与题面期望没有冲突。

【5 边界与隐含要求】
- `contentEditable={null}` 也应该不抛错。
- 从 `true` 更新为 `undefined`，应当把已有的 `contenteditable` 属性移除。
- `contentEditable={false}` 或 `"false"` 应当保持 `contenteditable="false"`，不能被当作移除。
- 现在的 `value === false` 分支会移除属性，可能要单独处理。
- 如果改成统一在赋值前判断 `null`，要避免破坏 `value`、`className` 等现有的清空行为（清空为 `''`）。
- SVG 元素不受影响，因为 `!isSvg` 已排除它们。
- 要注意包体积：仓库对 `props.js` 的字节数敏感，通常有 size 限制检查。

【6 改动规模】
- 源码只改 `src/diff/props.js` 一个文件，一两处，属于局部修补。
- 测试在 `test/browser/render.test.js` 里新增一两个用例。
- 不需要新增结构，也不贯穿多层。

【7 难点一句话】
- 修法本身很小，难在选对方案：既要让 `undefined/null` 不抛错，又不能破坏其他属性清空为 `''` 的行为，同时还要兼顾包体积。