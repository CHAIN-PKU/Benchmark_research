**仓库档案：xlink:href 被转成 hhref**

**【1 题面要点】**
- 要求的行为：SVG 元素上的 `"xlink:href"` prop 应渲染成 `href` 属性。`xlinkHref` 已经能正确转成 `href`。
- 复现：不用 JSX，直接调用 createElement。写法是 `createElement("svg", {}, createElement("use", { "xlink:href": "#foo" }))`。
- 期望输出：`<use>` 的 `href="#foo"`。
- 实际输出：`hhref="#foo"`。
- 修法建议（原文）：`Presumably the [H:h] should be either [H:h]+ or (H|:h)`。提出者愿意提 PR，但不确定选哪个更好。
- 题面没有给测试代码，也没说要不要同时处理其他 xlink 属性。

**【2 相关代码】**
- `src/diff/props.js:109`：`name = name.replace(/xlink[H:h]/, 'h').replace(/sName$/, 's');`，位于 `if (isSvg)` 分支（105-109 行）。
- 这是唯一的根因。
  - `[H:h]` 是字符类，匹配单个字符 `H`、`:` 或 `h`。
  - `xlink:href` 中的 `xlink:` 被替换成 `h`，结果是 `h` + `href` = `hhref`。
  - `xlinkHref` 里 `xlinkH` 被替换成 `h`，结果是 `href`，所以它是对的。
- `src/diff/props.js:107` 的注释本身就写着 `xlink:href / xlinkHref --> href`，所以意图是明确的。
- `setProperty`（props.js:56）由 `diffProps`（13-34 行）调用，`src/diff/index.js:443, 450` 也会调用它（那两处 isSvg 传 false）。

**【3 并列与牵连】**
- `className → class` 的 `/sName$/` 替换在同一行，写法同样脆弱，但不是本题的目标。
- `src/` 里没有第二处 xlink 处理。
  - 对 `compat`、`hooks`、`debug` 下的 `.js` 搜过，没有 xlink 的处理。
  - `compat/src/render.js` 只处理 class/className。
- `test/fixtures/preact.js:127` 是旧版 Preact 的快照，用 `/^xlink:?/` 配合 `setAttributeNS`。它是测试用的对照基线，不用改，也不是当前行为的规范。
- 改动只影响 isSvg 为真时的属性名。`oldProps` 的移除路径（props.js:18）同样走这个替换，所以设置和移除两边的名字保持一致。
- 副作用：任何 SVG 属性名里含有 `xlink` 加 `H`、`h` 或 `:` 的，都会受影响。例如 `xlink:title`、`xlinkTitle` 不会被命中，因为后面不是 h。

**【4 现有测试与约定】**
- `test/browser/svg.test.js:48` 用 `<svg viewBox="0 0 360 360" xlinkHref={url}>`，断言在 68 行：`<svg viewBox="0 0 360 360" href="www.preact.com">`。
  - 其中的 `html.replace(' xmlns:xlink="http://www.w3.org/1999/xlink"', '')`（63、81 行）是为了去掉某些浏览器自带的命名空间声明。
  - 这与题面期望一致，没有冲突。
- 没有任何现有测试覆盖 `xlink:href`，所以隐藏测试很可能是在 svg.test.js 里新增一个用 createElement 的用例，断言 `href` 是 `#foo`。
- 注释写明约定：`xlink:href was removed from SVG and isn't needed`，即统一成 `href`，不使用命名空间属性。
- 其他 xlink 属性（`xlinkActuate`、`xlinkRole` 等，见 `src/jsx.d.ts:294-300`）没有被特殊处理，原样设置。

**【5 边界与隐含要求】**
- 要同时保证 `xlinkHref` 和 `xlink:href` 两种写法得到 `href`。
- 不能误伤其他 xlink 属性：`xlink:title`、`xlinkRole` 等不应被改动。
- 大小写：`xlink:Href` 之类很少见，一般不用处理。
- 简单修成 `/xlink[H:h]+/` 之类的写法时，要检查 `xlink:h` 开头的其他属性。
- 仓库对体积很敏感（见 props.js:122「labelled break is 1b smaller」之类的注释），所以修法应尽量短。
- 需要用 `className` 的 `sName$` 替换配合：先替换 xlink，再替换 sName，顺序不变。

**【6 改动规模】**
- 1 个源文件、1 行（props.js:109），加 1 个测试用例。
- 是局部修补，不需要新增结构。
- 如果采用正则的另一种写法，如 `/xlink(H|:h)/`，只改这一行。

**【7 难点一句话】**
- 难点基本只在于看出 `[H:h]` 是字符类，而不是「H 或 :h」；改法是一行正则，题面已经给出两种方案，所以这道题整体很简单。