**档案：`Style/RedundantFreeze` 把 `"#@a/#@b"` 当成无插值字符串**

我没有实际运行 rubocop，下面的 AST 形状是读代码推断的。

**【1 题面要点】**
- 要求的行为：在 `# frozen_string_literal: true` 下，`"#@qwe/#@rty".freeze` 不应报 `Style/RedundantFreeze`。这类 `#@ivar`、`#@@cvar`、`#$gvar` 简写本身就是插值，字符串不会被冻结。
- 题面给了复现和期望输出（见 issue 原文）：
  - `ruby test.rb` 输出 `s1.frozen?` 为 true、`s2.frozen?` 为 false。
  - 期望 `rubocop test.rb` 无 offense。
  - 实际报 `5:6: C: [Correctable] Style/RedundantFreeze`。
- 题面没有给修法建议。

**【2 相关代码】**
- `lib/rubocop/cop/mixin/frozen_string_literal.rb:31-33` 的 `uninterpolated_string?` 是根因：`node.str_type? || (node.dstr_type? && node.each_descendant(:begin).none?)`。
  - 它用有没有 `begin` 后代来判断是否插值。
  - `#{...}` 会产生 `begin` 节点，`#@x` 不会。
  - 推断 `"#@x"` 解析为 `dstr(ivar)`，没有 `begin`，所以被判成无插值。
- `frozen_string_literal.rb:21-29` 的 `frozen_string_literal?`：
  - Ruby ≥ 3.0 时调用 `uninterpolated_string? || uninterpolated_heredoc?`，再与 `frozen_string_literals_enabled?` 取与。
  - Ruby < 3.0 时按类型 `%i[str dstr]` 判断，与插值无关，不受影响。
- `frozen_string_literal.rb:35-39` 的 `uninterpolated_heredoc?`：判断 `dstr`、是 heredoc 且 `children.all?(&:str_type?)`。
  - 这个写法对 `#@x` 已经正确，因为 ivar 子节点不是 str。
  - 所以 heredoc 里的 `#@x` 已经没问题，只有普通字符串有 bug。
- `lib/rubocop/cop/style/redundant_freeze.rb:39-46` 的 `immutable_literal?`：先 `strip_parenthesis`，再调用 `frozen_string_literal?(node)`。

**【3 并列与牵连】**
- 改 mixin 的 `uninterpolated_string?` 会同时影响所有调用方：
  - `lib/rubocop/cop/style/redundant_interpolation_unfreeze.rb:36` 直接调用它。
    - 该 cop 对 `"#@x".dup` / `+"#@x"` 现在会漏报（实际有插值，却因 `uninterpolated_string?` 为真而 return）。
    - 修复后它会开始报这类情况，这是行为变化。
  - `lib/rubocop/cop/style/mutable_constant.rb:152` 和 `:163` 经 `frozen_string_literal?` 调用。
    - `CONST = "#@x"` 在 frozen 注释下现在被当成已冻结，不报 `MutableConstant`。
    - 修复后会开始报，并自动加 `.freeze`。
    - 这个修正在语义上是对的，但要核对 mutable_constant 现有 spec 有没有冲突。
  - `Style/EmptyLiteral`、`Style/RedundantFetchBlock` 也 include 了该 mixin。
- 需要同时修正的并列点是 `#@@x`、`#$x`，以及 `#$1` 这类 nth_ref/back_ref，它们都是简写插值。

**【4 现有测试与约定】**
- `spec/rubocop/cop/style/redundant_freeze_spec.rb:40` 是 `it_behaves_like 'mutable objects', '"top#{1 + 2}"'`。
  - `:124` 和 `:130` 是 `it_behaves_like 'mutable objects', '"#{a}"'`。
  - 这些只测了 `#{}` 形式，没有 `#@` / `#$` 的用例。
  - 隐藏测试大概率是在这里加 `'"#@a"'` 等 mutable-objects 用例。
- 其他 spec 里有 `#@var` 的用例（`redundant_interpolation_spec.rb:59`、`variable_interpolation_spec.rb:72`），说明仓库认可这种写法属于插值。
- Ruby 语义本身就是规范：`#@x` 插值后的字符串不冻结。与题面期望不冲突。
- 我没有查 `mutable_constant_spec.rb` 里有没有 `#@` 用例。上面的 grep 只命中了 dstr / interpolation 相关行（124、145、178 等），没有直接命中 `#@`。

**【5 边界与隐含要求】**
- 要覆盖 ivar、cvar、gvar，以及 nth_ref / back_ref（`"#$1"`、`"#$&"`），覆盖不全的话隐藏测试可能会挂。
- 要覆盖混合字符串，如 `"a#@x/b"`，它的 dstr 子节点是 str 加 ivar。
- 带 `#{}` 的 `begin` 判断必须保留。
- 多行 `"a" "#@x"` 是相邻字面量拼接，嵌套 dstr 的情况。`each_descendant` 能递归，但如果改成只看直接子节点就会漏。
- 要检查改动是否破坏了无插值的普通 `"foo"`、`"a" "b"`。
- 改动应附带 changelog 条目（`changelog/` 目录有 `fix_*.md` 约定）。

**【6 改动规模】**
- 局部修补，核心只改 mixin 里 `uninterpolated_string?` 一处，约 1 个文件、1–3 行。
- 外加 spec 用例和一个 changelog 文件。
- 不需要新结构，也不需要贯穿多层。

**【7 难点一句话】**
难点不在改法，而在先判断出 `#@x` 的 AST 里没有 `begin`，再选一个对 `#@x`、`#@@x`、`#$x`、`#$1` 都成立的判据（比如检查子节点是否全为 str），同时留意改动对 `RedundantInterpolationUnfreeze` 和 `MutableConstant` 的连带影响。