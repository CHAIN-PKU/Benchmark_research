**【1 题面要点】**
- 要求：`statement_indentation` 在 `if/while/for/foreach/else` 等控制结构的主体没有花括号时，也要正确缩进，不能要求用户加花括号。
- 复现：issue 给了输入代码。
```
while ($str[$q] != '|')
    if (++$q >= $endptr)
        break 2;
```
- 实际输出：
```
while ($str[$q] != '|')
if (++$q >= $endptr)
break 2;
```
- 期望输出：issue 没有单独列出，只能从输入推断，即保持原有的层层缩进。
- 修法建议：没有。配置是默认配置，运行版本是 latest。

**【2 相关代码】**（均在 `src/Fixer/Whitespace/StatementIndentationFixer.php`，共 701 行）
- `applyFix` 122-526，是一个逐 token 的作用域栈状态机。
  - 作用域类型有 `block`、`block_signature`、`statement` 三种，字段有 `end_index`、`initial_indent`、`is_indented_block`。
- 204-271：遇到 `{`、`(`、`:` 等 token 时压入 `block` 作用域，`is_indented_block` 为 true。
- 273-306：遇到 `$blockSignatureFirstTokens`（126-143，含 T_IF、T_ELSE、T_WHILE、T_FOR、T_FOREACH、T_SWITCH 等）时压入 `block_signature`。
  - 274-294 的循环向后扫描，遇到 `{`、`;`、`=>`、`implements` 就停，遇到 `:` 就登记为备选语法。括号会被整体跳过。
  - **无花括号时，这里停在主体第一个 `;`，不是控制结构头的结束位置。**
  - 该作用域的 `is_indented_block` 为 false（302 行，只有 extends/implements 为 true）。
- 377-461：处理换行空白。
  - `block` 和 `block_signature` 作用域用 `initial_indent` 加上可选的一级缩进（`$indent`）。
  - `$indent` 只在 `is_indented_block` 为真时才可能为真（380 行）。
  - 所以无花括号主体的每一行都被写成控制结构那一行的缩进。这就是 bug 的症状。
- 495-524：弹出已结束的作用域，并把普通语句压成 `statement` 作用域。
- 528-557 `findStatementEndIndex`：按 `;`、`,`、`}`、`?>` 找语句结尾。
- 600 `getLineIndentationWithBracesCompatibility` 和 622 起的注释处理，是配套辅助方法。

**【3 并列与牵连】**
- 没有需要同步改的并列实现，但同一个文件里有多处相关逻辑：
  - 273-306 的 `block_signature` 分支，和 314-350 的 T_FUNCTION 分支，结构几乎相同（都是向后扫描到 `{` 或 `;`）。
  - 215-235 压入 `block` 作用域的分支。
  - `findStatementEndIndex` 用来确定主体结束位置。
- 参考实现：`src/Fixer/ControlStructure/ControlStructureBracesFixer.php:60-110`。
  - 它用 `findParenthesisEnd`，再看括号后的 token 是 `;`、`{`、`:` 还是 T_CLOSE_TAG，来判断有没有花括号。
  - 它还处理主体本身又是 `if/for/foreach/switch/while` 的嵌套情形，并按 `findStatementEnd` 找无花括号主体的结尾。
- 影响面：
  - `statement_indentation` 被 PSR2Set、SymfonySet 引用。
  - 还有集成测试 `tests/Fixtures/Integration/priority/braces_position,statement_indentation.test` 和 `misc/issue_7293.test`、`misc/no_multiple_statements_per_line,statement_indentation.test`。
  - 另外 `BracesFixer` 把它作为 `bracesFixerCompatibility` 的使用方。
  - 改核心作用域逻辑可能影响所有带花括号的既有用例，所以要全量跑这个测试文件。

**【4 现有测试与约定】**
- `tests/Fixer/Whitespace/StatementIndentationFixerTest.php`：数据提供器 `provideFixCases` 从 41 行开始，格式为 `[expected, input, config]`。
  - 例如 43-50 行 `'no brace block'`，注意它说的是整个文件没有花括号块，不是控制结构无花括号。
  - 我 grep 了以 `if (...)`、`while (...)`、`else` 结尾而无 `{` 的行，没有找到现有用例。**当前测试没有覆盖无花括号主体。**
- 备选语法有测试：815 行 `'alternative syntax'` 用 `if (1): ?> ... endif`，所以 `:` 形式已被支持。
- 107 行有一条 `@TODO`，说明当前对同一行多个括号的处理本来就有已知缺陷。
- 没有发现与题面期望冲突的现有断言。
- 约定：缩进用 `$this->whitespacesConfig->getIndent()`，换行用 `computeNewLineContent`（161 行）。没有外部规范文件。

**【5 边界与隐含要求】**
- 嵌套无花括号：`while` 套 `if` 套 `break`，需要逐层多缩进一级，这是题面的例子。
- `if ... else` 且两边都无花括号。
  - `else` 本身要回到 `if` 的缩进。
  - `else if` 的情形，参考 `ControlStructureBracesFixer` 在 62-66 行对此特判跳过。
- `elseif` 链、`for`、`foreach`、`do ... while`（`do` 不在 `$blockSignatureFirstTokens` 里）。
- 主体在同一行（`if ($a) foo();`）时不应受影响。
- 头部括号内多行，如参数跨行。
- 主体里有注释，或有嵌套花括号块，例如无花括号 `if` 的主体是一个带花括号的 `foreach`。
- 主体用 `?>` 结束；与备选语法、`switch/case` 并存。
- 与 `bracesFixerCompatibility` 模式交互。
- 主体是 `match` 或闭包，里面含有 `;`，扫描时要整体跳过。
- 已缩进正确的输入不能被改动，即保持幂等。

**【6 改动规模】**
- 源码基本只改 `StatementIndentationFixer.php` 一个文件，另在测试文件中补用例。
- 局部修补是可能的：
  - 在 273-306 分支里识别出头部结束后没有 `{`、`;`、`:`，当前行动态添加一级缩进。
  - 或者新增一种作用域类型。
- 如果要贯穿作用域栈，需要给作用域结构加字段，并同步 `@var` 注释类型（178-187）。
- 要改的点集中在 273-306、377-461、495-524 这三处，加上新逻辑或辅助方法。

**【7 难点一句话】**
这个修复器是靠一个隐式作用域栈工作的，而 `block_signature` 当前把扫描停在主体第一个 `;`，也不会给主体加缩进。要在不破坏大量已有带花括号用例的前提下，正确处理无花括号主体的嵌套和 `else` 配对，并且没有现成测试可以参照。