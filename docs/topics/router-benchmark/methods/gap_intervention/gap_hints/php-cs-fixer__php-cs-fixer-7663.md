## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 位置（均在 src/Fixer/Whitespace/StatementIndentationFixer.php）
1. applyFix 里的 $blockSignatureFirstTokens 和 block_signature 作用域（约 126–306 行）：作用域在遇到 `{`、`;`、`=>` 或 `:` 时结束。无花括号时，头部结束之后下一行的缩进由什么决定，请查清楚。`(` 分支（207–271 行）单独建了 block 作用域，要看括号结束后控制权怎么回到签名作用域。
2. 列表有 if/else/elseif/for/foreach/while/switch/try，没有 T_DO，也没有 declare。`do stmt; while()` 和 else 后无花括号是否同类问题；for/foreach/else/elseif 也是同类情形。
3. 约 505–524 行的 statement 作用域和 findStatementEndIndex（约 528 行起）：无花括号 body 本身是一条语句，可能还是另一条控制语句（题面里 if 嵌在 while 里，再嵌 break），要看语句结束位置的计算能否处理嵌套。

B. 边界输入
- 多层嵌套的无花括号 body，if / else if / else 链，foreach 套 if 套 break；每层都要多缩进一级。
- body 前后有注释或空行（isCommentWithFixableIndentation 与约 475–484 行的注释处理）。
- body 含多行表达式（数组、调用、闭包）。
- 无花括号语句后紧跟 `}` 或文件结尾。
- 交替语法（if: endif;）和 case/default 行为不应变化；在花括号里嵌套无花括号语句也要核对。

C. 已有约定
- tests/Fixer/Whitespace/StatementIndentationFixerTest.php 的数据提供器（如 provideFixCases）：先找已有的无花括号用例，核对预期，不要破坏；按已有格式补用例，覆盖 bracesFixerCompatibility 为 true 的构造方式。
- getDefinition() 的代码示例、getPriority()。
- BracesFixer 及其测试：bracesFixerCompatibility 分支（skip 和 getLineIndentationWithBracesCompatibility）为它服务，两种模式结果要一致。
- 配置项 stick_comment_to_next_continuous_control_statement 与 else/elseif 有关，不要影响它。

D. 提交前自测
1. 题面原样输入：while 下接 if，再接 break 2;，预期每层各缩进一级，再次运行结果不变（幂等）。
2. `if (a) x(); else if (b) y(); else z();` 每个分支分行写；再试 foreach/for/do-while 的无花括号版本。
3. 无花括号控制语句放在类方法花括号内部，后面还有其他语句和注释，确认后续缩进不被带偏，并且整个已有测试文件仍然通过。
