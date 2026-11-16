**档案：Hugo 内嵌 render-image 钩子不输出 Markdown 属性**

**【1 题面要点】**
- 要求的行为：内嵌（embedded）的图片渲染钩子要输出 Markdown 属性。
- 复现用例：开启 `wrapStandAloneImageWithinParagraph = false` 和 `markup.goldmark.parser.attribute.block = true`。内容是 `![alt](a.jpg)\n{.foo}`。
- 单语言站点（`[languages.en]` 不加 weight）时，输出是 `<img src="a.jpg" alt="alt" class="foo">`，此时用的是 goldmark 默认渲染。
- 去掉 `# weight` 的注释变成 `weight = 1` 后，站点被判定为多语言，内嵌钩子被启用，`class="foo"` 丢失。这是失败的断言。
- 期望输出：`<img src="a.jpg" alt="alt" class="foo">`，属性顺序为 src、alt、class。
- 题面没有给修法建议，只有测试用例和一个论坛链接。

**【2 相关代码】**
- `tpl/tplimpl/embedded/templates/_default/_markup/render-image.html:1-14`
  - 这是主要的改动点。
  - 它只构造了 `dict "alt" .Text "src" $src "title" .Title`，然后 range 输出，完全没有使用 `.Attributes`。
  - 输出格式是 `<img` 加各属性，以 `>` 结尾，没有 `/`。
- `markup/goldmark/render_hooks.go:~150-200`
  - `renderImage` 已经把非内部属性放进 `imageLinkContext.linkContext.AttributesHolder`，所以模板里的 `.Attributes` 有值。
  - 它用 `filterInternalAttributes` 去掉带内部前缀的属性（block 标记、ordinal 等）。
- `render_hooks.go:~204-232`：`renderImageDefault` 是不走钩子时的默认路径。
- `markup/internal/attributes/attributes.go:58`：`attributes.New` 会丢弃 `on*` 事件属性。`AttributesHolder.Attributes()` 在 `:148` 返回 map。
- `config/allconfig/allconfig.go:918-922`：多语言站点时，把 `RenderHooks.Link/Image.EnableDefault` 设为 true，这就是用例里 weight 触发差异的原因。
- `hugolib/page__per_output.go:478-485`：对内嵌模板，只有 `IsEnableDefault()` 为 true 才使用。

**【3 并列与牵连】**
- 并列实现：`render-link.html` 同样只用 `dict "href" "title"`，也没有输出 `.Attributes`。
  - `linkContext` 对链接传的是 `attributes.Empty`（`render_hooks.go:~281`），因此链接是否一并修复取决于范围。
  - 题面只提图片。
- 钩子模板的上下文是 `imageLinkContext`，它内嵌 `linkContext`。
- `render-codeblock-goat.html:1-3` 是已有的 `.Attributes` 用法参考。它用 `.Attributes.width` 等点取值，没有 range。
- 影响面：所有使用内嵌图片钩子的站点（多语言站点默认启用，或显式配置 `enableDefault`）。
- 图片资源解析 `$src` 的逻辑要保留。
- 依赖 `src`、`alt`、`title` 输出的现有测试可能受影响，要注意属性顺序和覆盖关系。

**【4 现有测试与约定】**
- `markup/goldmark/images/images_integration_test.go:39-60` 的自定义钩子测试用 `{{ .Attributes.class }}` 取值。
  - 断言是 `<figure class="b">`。
  - 说明 `.Attributes` 对图片钩子已经可用。
- `hugolib/content_render_hooks_test.go:101` 是自定义钩子测试，没有涉及属性。
- 没有找到测试内嵌 render-image 输出属性的用例。
- 我没有逐个检查所有测试里对内嵌钩子输出的字符串断言。
- 约定：默认渲染 `renderImageDefault` 的输出顺序是 src、alt、title，再加属性（`RenderASTAttributes`）。属性值要做 HTML 转义。
- 与题面期望没有冲突。期望的 `class="foo"` 排在 `alt` 之后，与默认渲染一致。

**【5 边界与隐含要求】**
- 属性与 src、alt、title 同名时的优先级。
- 属性值为非字符串类型（布尔、数字、`[]byte`）时的输出方式。`AttributesHolder.Attributes()` 返回的值类型不确定，模板里 `printf "%q"` 可能把非字符串值输出成不符合预期的形式。
- 值为空或为 false 时是否跳过。现有 `if $v` 会跳过空值。
- 属性的输出顺序：map 的 range 按键排序，所以 class 会排在 alt 前面。
  - 期望的 `src alt class` 顺序可能需要显式控制，不能直接把属性并入同一个 dict 再 range。
  - 这很可能是顺序断言的难点。
- HTML 转义：`safeHTMLAttr` 与 `%q` 的组合需要确认对特殊字符是否安全。
- 如果修改 `render-link.html`，还要先让 `linkContext` 传入真实属性。

**【6 改动规模】**
- 最小改动：只改 `render-image.html` 一个文件，几行。
- 如果连带处理 link：再改 `render-link.html`，并改 `render_hooks.go` 的 `renderLink` 传入属性。
- 需要加测试，大概在 `hugolib` 或 `images_integration_test.go` 里。
- 属于局部修补，不涉及新增结构。

**【7 难点一句话】**
改动本身很小，难点在于模板里如何按预期顺序（src、alt、title，再到 class 等属性）输出属性并保证转义安全，以及定位出原因是多语言站点启用了内嵌钩子，而不是 goldmark 解析的问题。