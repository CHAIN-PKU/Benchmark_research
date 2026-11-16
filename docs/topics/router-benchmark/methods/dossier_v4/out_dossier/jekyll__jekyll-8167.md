**【1 题面要点】**
- 目标行为：`slugify` 不能把泰米尔语的元音符号、组合符（如 U+0BCD virama）当成分隔符。文件名 `மல்லிப்பூ வகைகள்.md` 应得到 `மல்லிப்பூ-வகைகள்.html`。
- 现状：输出 `மல-லிப-பூ-வகைகள.html`，词在组合符处被断开。
- 根因（题面已给出）：`[:alnum:]` 对应 Alphabetic 属性，不包含部分 Mark（Mn/Mc）。
- 修法建议原文：“change the Regex to match `/[^\p{M}\p{L}\p{Nd}._~!$&'()+,;=@]+/`”。
- 没有给最小复现脚本，只有期望文件名和实际文件名。

**【2 相关代码】**
- `lib/jekyll/utils.rb:16`：`SLUGIFY_DEFAULT_REGEXP = Regexp.new("[^[:alnum:]]+")`。default 模式，也是 `mode` 为 nil 时的模式。
- `lib/jekyll/utils.rb:17`：`SLUGIFY_PRETTY_REGEXP = Regexp.new("[^[:alnum:]._~!$&'()+,;=@]+")`。pretty 模式。题面引用的正是这条。
- `lib/jekyll/utils.rb:18`：`SLUGIFY_ASCII_REGEXP`。只保留 A-Za-z0-9，不应改。
- `lib/jekyll/utils.rb:15`：`SLUGIFY_RAW_REGEXP`，只处理空白。
- `lib/jekyll/utils.rb:345-365`：`replace_character_sequence_with_hyphen` 按 mode 选正则，再 `gsub(..., "-")`。
- `lib/jekyll/utils.rb:201-223`：`slugify` 入口。latin 模式先用 `I18n.transliterate`，再走 default 的正则。第 218 行去掉首尾连字符，第 220 行 `downcase!`。
- `lib/jekyll/utils.rb:168-175`：文档注释里写着“non-alphabetic characters”，可能要顺带改措辞。

**【3 并列与牵连】**
- default 和 pretty 两条正则需要同样改动，ascii 和 raw 不动。
- latin 模式复用 `SLUGIFY_DEFAULT_REGEXP`（走 `else` 分支），会自动受影响。
- 调用点（改正则后都会受影响）：
  - `lib/jekyll/filters.rb:62-63`：Liquid 的 `slugify` 过滤器。
  - `lib/jekyll/drops/url_drop.rb:18`、`22-23`、`27`、`42`：`slug`、`title`、`name` 和 category 的 permalink 占位符。
- `lib/` 下除第 16、17 行外，没有其他 `[[:alnum:]]` 或 `\p{}` 用法。
- `docs/_docs/liquid/filters.md:95` 附近的 slugify 选项文档可能要同步。

**【4 现有测试与约定】**
- `test/test_utils.rb:157`：`assert_equal "كيف-حالك", Utils.slugify("كيف حالك؟")`。阿拉伯语标点“؟”被丢弃，它的 Unicode 类别是 Po，不在 `\p{M}\p{L}\p{Nd}` 里，所以仍然通过。
- `test/test_utils.rb:176`：`assert_equal "5時-6時-三-一四", Utils.slugify("5時〜6時 三・一四")`。“〜”（Pd）和“・”（Po）仍会被替换。
- `test/test_utils.rb:165`：`"the-config-yml-file"`。下划线属于 Pc，不在保留集里，所以仍被替换。
- `test/test_utils.rb:199`：pretty 模式的 `"the-_config.yml-file"`。
- `test/test_utils.rb:206-218`：ascii 和 latin 模式的断言。第 218 行 `"Aあわれ鬱господинZ"` 在 latin 模式下期望 `"a-z"`。transliterate 后非 ASCII 字符会变成 `?`，`?` 属于 Po，仍是分隔符，不受影响。
- `test/test_utils.rb:288`：`"💎"` 得到 `""`。💎 是 So，不在保留集里，仍然通过。
- `test/test_filters.rb:1254`、`1258`：过滤器测试。
- 没有现成的泰米尔语或 Mark 相关测试，隐藏测试很可能新增这类断言。
- 题面的建议正则与现有测试看起来没有冲突。我只做了静态推演，没有运行。

**【5 边界与隐含要求】**
- 数字只取 `\p{Nd}`，不含 Nl（罗马数字）和 No（上标数字、①）。`[:alnum:]` 原本会匹配这些，改了之后这类字符会变成连字符，行为有细微回退。要不要保留 `\p{N}`，取决于隐藏测试。
- 注意 `[:alnum:]` 在 Ruby 里本身已含 `\p{L}`、`\p{Nd}`、部分 Mn/Mc。
- 其他印度系文字（天城文、泰文等）的组合符同理，`\p{M}` 能一并覆盖。
- 下游：`slug.downcase!` 对 Mark 没有副作用。
- `Regexp.new("...")` 里写 `\p{}` 时，双引号字符串中的反斜杠要写成 `\\p`，或者改用正则字面量或单引号。
- 注释和文档措辞（“non-alphabetic”）可顺带更新。
- 可能要在 History 或 docs 里加一条记录，通常不影响测试。

**【6 改动规模】**
- 核心：`lib/jekyll/utils.rb` 改 2 行常量（第 16、17 行），加上可选的注释措辞调整。
- 测试：在 `test/test_utils.rb` 新增 1–2 个泰米尔语用例，default 和 pretty 各一个。
- 属于局部修补，不涉及新结构，也没有跨层。

**【7 难点一句话】**
代码改动只有两行正则，题面已给出答案；风险只在 `\p{M}\p{L}\p{Nd}` 与 `[:alnum:]` 的差异（Nl/No 的取舍）以及 `Regexp.new` 字符串里的转义，难度很低。