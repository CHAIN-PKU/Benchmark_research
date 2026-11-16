# 仓库档案：`simple_to_complex_string_variable` 不转换带下标的 `${name[...]}`

我读了修复器、它的测试、`BraceTransformer`、`SquareBraceTransformer` 和 `Tokens` 里相关的块定义，也做了 grep。这个环境里没有运行 PHP，所以下面写到分词结果的地方是我读代码推出来的，没有实测。

## 【1 题面要点】
- **要求的行为：** 修复器要把 `"Hello ${name['key']}!"` 改成 `"Hello {$name['key']}!"`。`"Hello ${name[0]}!"` 同样要改成 `"Hello {$name[0]}!"`。
- **现状：** 这两种写法目前原样输出，没有任何改动。
- **复现：** 给了。issue 要往 `SimpleToComplexStringVariableFixerTest.php` 的 `provideFixCases` 里、`'basic fix'` 之后加两条用例：`'array key access'` 和 `'array index access'`。输入和期望输出都已写全。
- **修法建议：** 没有。
- **题面没给的：**
  - heredoc 的情况。
  - 嵌套下标。
  - 前一个字符是 `$` 的情况。

## 【2 相关代码】
- **`src/Fixer/StringNotation/SimpleToComplexStringVariableFixer.php:73-109`**，`applyFix()`，是主要要改的地方。
  - 它从后往前扫描，找到 `T_DOLLAR_OPEN_CURLY_BRACES`（`${`）。
  - `:82-86` 要求下一个 token 是 `T_STRING_VARNAME`，否则 `continue`。
  - `:88-92` 要求 `$index+2` 恰好是 `CT::T_DOLLAR_CLOSE_CURLY_BRACES`，否则 `continue`。**这就是 bug 的根源。**
    - 带下标的写法里，`}` 前面还夹着 `[`、键、`]`，所以 `index+2` 不是关闭花括号，整个替换被跳过。
  - `:94-100` 处理 `$${name}` 的情形：前一个字符串 token 以未转义的 `$` 结尾时，把它改成 `\$`。
  - `:102-107` 用 `overrideRange($index-1, $index+2, ...)` 一次性替换四个 token，换成 `{`、`$name`、`}`，而且写死只替换 3 个 token 加前一个字符串 token。
- **`:75` 的循环上界 `count-3`** 是按 `${ name }` 三个 token 的长度写的。带下标时序列更长，但循环从后往前、只看起点，所以大概不受影响。
- **`:70` 的 `isCandidate`** 不用改。
- **`src/Tokenizer/Transformer/BraceTransformer.php:99-105`**，`transformIntoDollarCloseBrace`，决定关闭 token 是什么。
  - 它用 `getNextTokenOfKind($index, ['}'])` 找到**第一个** `}`，把它改成 `CT::T_DOLLAR_CLOSE_CURLY_BRACES`。
  - 这是朴素匹配，不数嵌套。
  - 对 `${name['key']}` 和 `${name[0]}` 够用，因为键里没有 `}`。
- **`:78-97`**，`transformIntoCurlyCloseBrace`，对 `T_CURLY_OPEN` 的关闭花括号会数层级。

## 【3 并列与牵连】
- **没有并列的重复实现。** 只有这一个修复器处理 `${`。
- **成对的修复器：** `ExplicitStringVariableFixer` 的 priority 说明（`:61-62`）写了本修复器 "Must run after ExplicitStringVariableFixer"。它的行为不需要同步改。
- **分词器：** `SquareBraceTransformer::isShortArray` 和 `isArrayDestructing`（`:117, :150`）把 `T_STRING_VARNAME` 放进了禁止前驱列表。
  - 这说明 `${name[...]}` 里的 `[` 会被当作普通索引括号，不会变成 `CT::T_ARRAY_SQUARE_BRACE_*`。
  - 所以 `[`、键、`]` 保持原样 token，可以原封不动搬过去。
- **其他调用点：** `T_STRING_VARNAME` 还被 `NonPrintableCharacterFixer:45,165` 和 `LambdaNotUsedImportFixer:177` 使用，改本修复器不会影响它们。
- **文档：** 修复器的 `getDefinition()` 和 `doc/rules` 文档由 `getDefinition` 生成。新增 `CodeSample` 的话，文档可能要重新生成。是否需要新增并不确定。

## 【4 现有测试与约定】
- **测试文件：** `tests/Fixer/StringNotation/SimpleToComplexStringVariableFixerTest.php:36-132`。
- **已有用例：**
  - `'basic fix'`：`${name}` → `{$name}`（`:38-49`）。
  - `'heredoc'`（`:51-68`）。
  - `'implicit'`：`"Hello $name!"` 不动（`:70-76`）。
  - `'implicit again'`：`"Hello { $name }!"` 不动（`:78-84`）。
  - `'escaped'`：`"Hello \${name}"` 不动（`:86-92`）。
  - `'double dollar'`：`$${name}` → `\${$name}`（`:94-105`）。
  - `'double dollar heredoc'`（`:107-124`）。
  - `'double dollar single quote'`：单引号字符串不动（`:126-132`）。
- **与题面的冲突：** 没有。现有用例都不涉及下标，题面新增的用例和它们互不矛盾。
- **外部规范：** PHP 的 `${expr}` 语法。
  - `"${name[0]}"` 等价于 `"{$name[0]}"`。
  - `"${name}"` 里的 `name` 是变量名，`${expr}` 里则是表达式，对应 `T_STRING_VARNAME` 与否。
  - 仓库里没有别的约定文件需要对照。

## 【5 边界与隐含要求】
- **heredoc 里的下标：** `${name['key']}` 和 `${name[0]}` 都应该转换。
- **前缀 `$`：** `$${name[0]}` 应像 `$${name}` 一样得到 `\${$name[0]}`。这是已有逻辑，应保留。
- **转义：** `\${name[0]}` 不应被修改。目前靠分词器把它当普通字符串，应该没问题。
- **多重下标：** `${name[0][1]}`、`${name['a']['b']}` 应该处理。
- **下标里不是简单常量的情况：** 例如 `${name[$i]}`、`${name[$i + 1]}`。
  - 它们能不能转，要看实现想覆盖到什么程度。
  - 保守做法是只处理 `[` 到 `]` 之间的一整段 token。
- **`${expr}` 不以变量名开头的情况**，例如 `${foo()}`、`${$a}`：`T_STRING_VARNAME` 不成立，应保持不动。现有逻辑已经保证这点。
- **键为未加引号的字符串：** `${name[key]}`。
  - 在 `${}` 里它是常量，转成 `{$name[key]}` 后语义不变。
  - 但这种写法不在 issue 的用例里，不确定隐藏测试是否涉及。
- **循环边界：** 如果把 `:75` 的 `count-3` 之类的上界按旧结构硬编码，替换之后的 token 偏移要重新核对。

## 【6 改动规模】
- **文件数：** 源码 1 个文件，即 `SimpleToComplexStringVariableFixer.php`。测试 1 个文件。
- **处数：** `applyFix` 里 1 处。
  - 把 `index+2` 必须是关闭花括号的硬编码，改成找到真正的关闭 token（用 `getNextTokenOfKind` 或 `findBlockEnd`）。
  - 然后把 `[ ... ]` 之间的 token 原样保留，再替换首尾。
- **性质：** 局部修补，不需要新增结构，也不跨层。
- **顺带的小改动：** 可能要在 `getDefinition` 里加 `CodeSample`，是否需要不确定。

## 【7 难点一句话】
**难点：** 现有代码把「`${` + 变量名 + `}`」当成恰好 3 个 token 来整体替换。要保持前缀 `$` 转义逻辑不变，又要让中间任意长度的下标 token 原样保留，改好后同时要保证不破坏现有的 `$${name}`、转义和 heredoc 用例。