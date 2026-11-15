## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) tpl/tplimpl/embedded/templates/_default/_markup/render-image.html 只构造 alt/src/title、不读 .Attributes，是最可能的修改点；render_hooks.go 的 renderImage 已把属性传入 imageLinkContext。2) render-link.html 同样写法，renderLink 的 AttributesHolder 为 attributes.Empty，注意范围，不要顺手改。3) renderImageDefault（无 hook）与嵌入模板是并列路径，核对属性处理一致。4) 题面失败只在配置 [languages.en] weight 后出现，需查 hugolib 中嵌入模板/render hook 的加载与多语言查找逻辑，定位 weight 为何改变结果。
B. 1) 多属性：{.foo #bar width=10}、id、data-*。2) 属性值含引号、<、& 的转义（现有用 printf %q + safeHTMLAttr）。3) 属性名与 alt/src/title 重名时谁优先。4) 行内图片 vs 独占一行块图片（wrapStandAloneImageWithinParagraph），内部属性 AttrIsBlock/AttrOrdinal 经 filterInternalAttributes 不能输出。
C. 1) render-codeblock-goat.html 用 .Attributes 读取属性，可参考写法。2) docs/content/en/templates/render-hooks.md 写链接 Attributes 恒为空，若行为改变文档可能需同步。3) markup/goldmark/images/images_integration_test.go 及 render hook 相关现有测试；嵌入模板输出可能被精确字符串断言（属性顺序、空白），改后全量跑相关包测试。
D. 1) 题面例子分别在无 weight 和有 weight 两种配置下运行，两次输出都应为 <img src="a.jpg" alt="alt" class="foo">。2) 无属性的普通图片输出与修改前完全一致，无多余空格或空属性。3) 同页两张图只有第一张带 {.foo #x}，第二张不应带属性；再测自定义 render-image 模板的站点不受影响。
