【1 题面要点】
- 要求的行为：格式化器不能把 `f"...{expr}..."` 里的插值表达式拆成多行。词法器会拒绝多行插值，所以格式化后的代码编译不过。
- 复现：题面给了一个例子，`f"You cannot use another ender pearl for {shared.format_duration(\n  remaining,\n)}."`。编译器报 `[error] Multi-line f-string interpolation` 和 `f-string interpolations must be single-line`。
- 期望输出（题面原话）：“Either Lisette formatter should preserve single-line interpolation in compatible cases, or Formatter rules should be configured to avoid splitting interpolation argument expressions across lines.”
- 题面没有给修法细节，没有给出格式化前的原文，`## Interface` 写明“No new interfaces”。
- 题面没说 f-string 太长、一行放不下时怎么处理。

【2 相关代码】
- `crates/format/src/formatter/expression.rs:230-249`，`format_string`。
  - 它把每个插值写成 `"{"` + `self.expression(e)` + `"}"`，再用 `concat` 拼起来，没有套 group，也没有任何防断行的措施。
  - 插值里的表达式用的是普通的可断行文档。
  - 这个 f-string 文档位于外层 group 之内。外层放不下 80 列时，里面的 `strict_break` 会进入 Broken 模式，于是被拆成多行。
- `crates/format/src/expression.rs:590-723`，`call` 和 `format_call_with_head`。这里生成 `head ( strict_break("","") body ) group`，是题面例子里被拆开的来源。
- `crates/format/src/formatter/expression.rs:213-228` 的 `slice` 是另一类会断行的结构。`call` 里还有方法链（`format_method_chain`），题面例子的 `shared.format_duration(...)` 就是单段方法调用。
- `crates/format/src/lindig.rs` 是 Wadler/Lindig 风格的文档引擎，宽度固定为 80，见 `lib.rs:12 MAX_LINE_WIDTH` 和 `lib.rs:29`。
  - 文档类型有 `Group`、`Nest`、`StrictBreak`、`FlexBreak`、`ForceBroken`、`NextBreakFits`、`VerbatimText`。
  - `Group` 在 `format()` 里只用 `fits()` 判断整组能否放进一行（lindig.rs:194-201）。
  - 没有“强制不换行”的原语。`Mode::ForcedUnbroken` 只能通过 `NextBreakFits(_, false)` 间接得到。
- `crates/syntax/src/lex/errors.rs:225-236` 定义了该错误，错误码是 `format_string_multiline_interpolation`，帮助信息是“Extract the expression into a `let` binding”。

【3 并列与牵连】
- 并列的断行点有多处，都可能出现在插值里：调用参数、slice、方法链、struct 调用（`struct_call`，expression.rs:823）、二元表达式、match、闭包、block 等。
  - 修复需要通用，不能只改调用。
  - 最直接的办法是在 `lindig.rs` 里新增一种“强制 flat”渲染，或者在构造文档时让插值内所有 break 都走 unbroken 分支。
  - 也可以在 `format_string` 里把表达式文档渲染成单行字符串，作为 `Document::string` 使用。
- `sequence.rs:226-254, 338` 和 `comments.rs:377` 会单独调用 `to_pretty_string(80)` 渲染子文档。如果采用“渲染成字符串”的做法，要注意这几处和它的关系。
- 插值里的表达式如果含有 block、match 或 closure，这些结构会用 `force_break` / `Newline`，flat 渲染也压不平。这种情况本身就无法写成单行，需要决定怎么处理。
- 影响面：所有含 f-string 的格式化输出，包括 stdlib 和示例代码的格式化快照。
- 注释：插值内部表达式的注释通过 `self.comments` 游标消费，改动文档构造方式时要保持游标顺序正确。

【4 现有测试与约定】
- 格式化测试在 `tests/spec/format/mod.rs`，用 `assert_format_snapshot!("源码")`，快照放在 `tests/spec/format/snapshots/*.snap`。
- 相关现有用例：
  - `mod.rs:306` 的 `format_string`：`fn test() { f"hello {name}" }` 输出 `f"hello {name}"`。
  - `mod.rs:1448` 的 `format_fstring_multiline_text_roundtrip`：文本部分含换行时原样保留，也就是 `Text(s) if s.contains('\n')` 走 `verbatim`。
  - `mod.rs:1438` 的 `format_string_multiline_roundtrip`。
- 词法侧已有快照：`tests/ui/errors/snapshots/lex_format_string_multiline_interpolation.snap` 和 `lex_format_string_unclosed_brace_at_newline.snap`。这说明单行插值是语言规则，格式化器应该遵守。
- 与题面期望不冲突：题面期望“保持单行”，现有测试只覆盖短 f-string，不覆盖超长插值。
- 没找到现成的参考实现，格式化器里没有类似的“保持单行”处理。
- 隐藏测试大概率是新增 `.snap` 用例，输入是超过 80 列、插值里有调用的 f-string，期望插值保持单行。具体输出（f-string 整体超宽，还是外层其他结构换行）要靠快照确定。

【5 边界与隐含要求】
- 超过 80 列时，f-string 本身允许变长。插值内部不换，但外层结构（比如外层调用的参数）仍然可以换行。需要避免“整体因为 f-string 放不下而把外层也拆开”造成多余输出，也要避免 fits 计算把含 `Newline` 的内容当成放得下。
- 多个插值、嵌套 f-string（插值里再有 f-string）、插值里含字符串字面量或带引号的调用。
- 插值内含多行 block / match / closure：本身就无法单行，需要决定回退策略。
- 插值内含注释。
- 格式化要幂等：对已经被旧格式化器拆成多行的输入重新格式化时，词法器会先拒绝这种源码，这种情况大概率不用处理。
- 带转义的文本部分和 `{{` / `}}` 不应受影响。
- 外层 group 判断是否放得下时，f-string 的宽度计算要合理（`fits` 在遇到 `StrictBreak` 且 Broken 模式时返回 true，可能低估宽度）。

【6 改动规模】
- 最小做法：改 1 个文件（`expression.rs` 的 `format_string`），再加快照测试。
- 如果引擎需要新原语（强制 flat 模式），要改 `lindig.rs` 的 `Document`、`fits` 和 `format` 三处，再改 `format_string`。
- 属于局部修补，不涉及贯穿多层的结构变更，通常 1-2 个源文件加 2-3 个快照。

【7 难点一句话】
难在 Lindig 引擎没有“强制不换行”的原语，而插值里任何可断行结构（调用、slice、方法链等）都会被外层 group 的 Broken 模式拆开，所以要在引擎里新增强制 flat 渲染，或者把插值预渲染成单行字符串，同时保证宽度计算和注释游标仍然正确。