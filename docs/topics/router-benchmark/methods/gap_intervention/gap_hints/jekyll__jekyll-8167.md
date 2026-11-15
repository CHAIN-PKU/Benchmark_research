## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
1. `lib/jekyll/utils.rb:16` 的 `SLUGIFY_DEFAULT_REGEXP` 和第 17 行的 `SLUGIFY_PRETTY_REGEXP` 都用了 `[^[:alnum:]…]`。题面只提到 pretty 模式。default 模式有同样的缺陷，用默认 permalink 或 `slugify` 过滤器处理泰米尔语标题时，会有同样的断词问题。
2. `latin` 模式在 `slugify`（约第 210–215 行）里先转写，再走 `replace_character_sequence_with_hyphen` 的 default 分支，所以会跟着 default 的正则一起变化。`latin` 模式依赖 `I18n.transliterate`，要核对它对组合符号的处理。
3. 调用点有 `lib/jekyll/drops/url_drop.rb`（`slug`、`title`、`categories` 等）和 `lib/jekyll/filters.rb:62` 的 `slugify` 过滤器，它们都走同一个方法。修改后应当全部生效，并且不能破坏现有行为。
4. `ascii` 模式（`SLUGIFY_ASCII_REGEXP`）本来就只保留 ASCII，不应该改动。`raw` 模式只处理空白，也不应该改动。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
1. 完整的题面例子 `மல்லிப்பூ வகைகள்`。期望结果是 `மல்லிப்பூ-வகைகள்`，只有空格变成连字符，组合符号 `U+0BCD`、元音符号等都要保留。
2. 其他带组合符号的文字，例如天城文、泰语、阿拉伯语的音符。已有的阿拉伯语测试 `كيف-حالك` 和日文测试 `5時-6時-三-一四` 不能退化。其中全角标点 `〜` 和 `・` 仍然要被替换成连字符。
3. 数字类别。如果改用 Unicode 属性类，要核对非 `Nd` 的数字（如罗马数字、上标数字）和原先 `alnum` 的行为差异。同时核对 emoji（`💎` 应得到空串）和标点是否仍会被替换。
4. 首尾连字符的去除（约第 218 行）、大小写处理（`downcase!`）和 `cased` 选项，对组合符号字符不应产生副作用。

**C. 仓库里已有的约定、文档或测试**
1. `test/test_utils.rb` 约 131–290 行是 slugify 的测试组，里面有 Unicode 的先例（阿拉伯语、日语）。新增的测试应当按同样的风格放在这里，并且要覆盖 default 和 pretty 两种模式。
2. `docs/_docs/liquid/filters.md` 第 101–105 行把模式描述为“非字母数字”。如果行为变了，要核对文档是否仍然准确。
3. `lib/jekyll/utils.rb` 约 158–200 行的 slugify 注释，以及 pretty 模式里保留 `._~!$&'()+,;=@` 的注释，也需要保持一致。
4. `test/test_filters.rb:1252` 附近有 slugify 过滤器的测试，`test/` 里还有 permalink、url 相关的测试，可能依赖现有行为，改完要跑一遍。

**D. 提交前建议额外自测**
1. 分别用 default 和 pretty 两种模式，对 `மல்லிப்பூ வகைகள்` 调用 `Utils.slugify`，核对结果。
2. 用文件名 `மல்லிப்பூ வகைகள்.md` 的文章走一遍 permalink 或 `url_drop` 的完整流程，检查生成的 URL。
3. 跑 `test/test_utils.rb`、`test/test_filters.rb` 以及 permalink 相关的测试，确认已有的阿拉伯语、日语、emoji 用例都没有变化。
