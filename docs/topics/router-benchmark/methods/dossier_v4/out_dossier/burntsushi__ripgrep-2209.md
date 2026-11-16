# 仓库档案：`--replace` 与 `--multiline` 组合时输出被扩大

## 【1 题面要点】
- **要求的行为**：带 `-U` 加 `-r '$usage'` 时，只应输出被匹配范围内替换后的内容，不应带出匹配范围之后的文本。
- **复现**：题面给了完整的输入文件 `patternfuncs.zsh` 和命令 `rg -NU -r '$usage' '^(?P<predoc>…)…(  #(?P<usage> .+))?'`。
- **期望输出**：只有一行 ` [-h] [-U|-u <pkgspec>[,<pkgspec>...]] [<reqs-in>...] [-- <pip-compile-arg>...]`。
- **实际输出**：这一行之后还多出了后面几行函数体，直到 `local gen_ha` 截断。
- **没有给修法建议。** 题面只对比了有无 `-r` 的输出差异。多出的内容恰好约 128 字节，与 `MAX_LOOK_AHEAD` 对得上，这是我的推断，题面没提。

## 【2 相关代码】
- `crates/printer/src/util.rs:55-107` 的 `Replacer::replace_all`，是最可能出问题的函数。
  - 多行模式下（`:65-69`）它把 subject 截到 `range.end + MAX_LOOK_AHEAD`（128，定义在 `crates/printer/src/lib.rs:86`）。
  - 之后调用 `matcher.replace_with_captures_at(subject, range.start, …)`（`:85-103`）。
  - 这个 subject 比匹配范围多出最多 128 字节的前瞻内容，而且整个 subject 都会进入替换结果。
- `crates/matcher/src/lib.rs:923-943` 的 trait 默认实现 `replace_with_captures_at`。
  - `:941` 的 `dst.extend(&haystack[last_match..])` 会把最后一次匹配之后到 haystack 末尾的全部内容追加进 dst。
  - 这正是多出来的尾巴的直接来源。
  - 同文件 `:902-913` 是 `replace_with_captures`，委托给 `_at` 版本。
  - `:1254-1278` 是 `&M` 的转发实现。
  - `crates/regex/src/matcher.rs:613-635` 是各后端（含 PCRE2 之外的几个枚举分支）的转发。
- `crates/printer/src/standard.rs:731-752` 的 `replace`。
  - `:809` 对匹配用 `mat.bytes_range_in_buffer()` 作为 range，传入的是整个 buffer。
  - `:839` 对 context 行用 `0..ctx.bytes().len()`。
- `crates/printer/src/util.rs:387-442` 的 `find_iter_at_in_context`。这是同类前瞻处理的参考实现，它用 `if m.start() >= range.end { return false }` 在 range 外截断。`replace_all` 没有这个截断。

## 【3 并列与牵连】
- **并列实现**：`find_iter_at_in_context`（`util.rs:387`）和 `replace_all` 用同一套「多行加前瞻」处理，修改时两处风格应保持一致。
- **调用点**：
  - `replace_all` 只被 `standard.rs:743` 调用。
  - `replace_with_captures_at` 在仓库内只被 `util.rs:86` 使用。
  - 上游 grep-matcher 是公共 trait，其默认实现有外部使用者，改它的语义会影响 API 行为。
  - 我没有逐个确认 `crates/pcre2`、`crates/regex` 是否覆盖该默认方法。`crates/regex/src/matcher.rs` 只做转发。
- **牵连的使用方**：
  - 替换结果通过 `Sunk::from_sink_match` / `from_sink_context`（`util.rs:192-213`、`standard.rs:939/954`）替代原始 bytes，之后用于只匹配、每匹配一行（per_match）、颜色输出、`--max-columns` 预览等路径。
  - 所以替换结果的边界要保证 `matches` 偏移仍然对应 dst。
- 我没有看到 JSON 和 Summary 打印器使用 `Replacer`。grep 只在 `standard.rs` 里命中。

## 【4 现有测试与约定】
- `crates/printer/src/standard.rs:3195-3451` 有一批替换单测，例如：
  - `:3221` `replacement`
  - `:3373` `replacement_max_columns_preview2`
  - `:3400` `replacement_only_matching`，断言 `"1:doctah Watsons MD\n1:doctah  MD\n…"`
  - `:3427` `replacement_per_match`
  - 这些是非多行，不受前瞻影响。
- `tests/regression.rs:748` `r1311_multi_line_term_replace`：`-U -r? -n "\n"` 对 `hello\nworld\n` 期望 `"1:hello?world?\n"`。这说明修复不能把匹配范围内的行终止符吃掉。
- `tests/regression.rs:949` `r1739_replacement_lineterm_match`：`-r${0}f '.*'` 对 `a\n` 期望 `af\n`。这是单行模式下的尾部行终止符行为，也不能被破坏。
- `crates/matcher/tests/test_matcher.rs:198-219` 测试 `replace_with_captures` 默认语义，会追加尾部内容。若修改 trait 默认实现，这两个测试可能要跟着改，这是潜在冲突点。
- **约定**：没有外部规范。正确行为由「有无 `-r` 时匹配范围应一致」决定，与题面期望不冲突。隐藏测试大概率是 `tests/regression.rs` 加一个以 issue 编号命名的新用例。

## 【5 边界与隐含要求】
- 前瞻内容仍必须能被正则看到。多行的 look-ahead 匹配（见 `util.rs:398-420` 的注释）不能因为收窄 subject 而失效。所以应该是截断输出，不是截断 subject。
- 最后一次匹配之后、range 内的尾部文本（如行终止符，见 `r1311`）要保留。
- 匹配开始于 range 之前、或结束于 range 之后的匹配如何处理。`find_iter_at_in_context` 的判断是 `m.start() >= range.end`。
- 单行模式下尾部行为（`r1739`）不能被改动。
- 若 `append` 返回 false 提前停止，剩余内容的处理要与新逻辑一致。
- `matches` 里记录的偏移必须仍与 dst 对应。

## 【6 改动规模】
- 局部修补，约 1 个文件、1 到 2 处，主要集中在 `crates/printer/src/util.rs` 的 `replace_all`。
- 如果选择改 trait 默认方法，则会涉及 `crates/matcher/src/lib.rs`，并可能影响 matcher 的测试，改动面稍大。
- 另需新增一个回归测试，约 1 处。

## 【7 难点一句话】
难点在于：定位出尾巴来自 `replace_with_captures_at` 默认实现的 `dst.extend(&haystack[last_match..])`，并且在不破坏前瞻匹配、`r1311`/`r1739` 和 matcher 默认语义的前提下，只把输出截在 range 内。我读到了相关代码，但没有运行复现。