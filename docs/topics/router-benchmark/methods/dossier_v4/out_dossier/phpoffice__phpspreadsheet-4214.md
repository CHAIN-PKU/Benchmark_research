# ROUNDDOWN 题仓库档案

## 【1 题面要点】
- 要求：`=ROUNDDOWN(249.9975,0)` 应返回 249，现在返回 250。
- 题面给了复现：`$calculation->calculateFormula('=ROUNDDOWN(249.9975,0)')`。期望输出是 249。
- 题面没有给修法建议。
- 作者只说 1.29.1 正常，1.29.2 和 3.3.0 有问题。
- 作者提到 php8.4 的舍入行为不同，但他用的是 php8.3，与此无关。
- 我没有运行代码，下面的根因来自读代码。

## 【2 相关代码】
- `src/PhpSpreadsheet/Calculation/MathTrig/Round.php:100-134`，`Round::down()`，是 ROUNDDOWN 的实现。
- 注册位置是 `Calculation.php:2227`，ROUNDDOWN 映射到 `Round::down`。
- 根因在第 117-133 行。对正数 `$digits=0`，算法是：
  - `$digitsPlus1 = 1`。
  - `sprintf("%.1F", 249.9975 - 0.5*0.1**0)`，即 `sprintf("%.1F", 249.4975)`，得 "249.5"。
  - `round(249.5, 0, PHP_ROUND_HALF_UP)`，得 250。
- 这是二次舍入：先用 sprintf 舍入到 digits+1 位，再用 round 舍入到 digits 位。
- 原本想用 -0.5 偏移再四舍五入来实现向零截断，但 sprintf 的中间舍入把 .4975 变成了 .5，随后 HALF_UP 进位。
- 变更日志 `CHANGELOG.md:106` 写着："New Algorithm for TRUNC, ROUNDUP, ROUNDDOWN. Issue #4113"。这个新算法就是回归的来源。
- `Round::down` 的 `round(..., PHP_ROUND_HALF_UP)` 在 digits 位上做的是最近舍入，不是向零截断。

## 【3 并列与牵连】
- `Round::up()`（第 53-86 行）是镜像实现，结构完全相同，用 +0.5 偏移、sprintf、`PHP_ROUND_HALF_DOWN`。我推断它有同类的二次舍入缺陷。
  - 例如 `ROUNDUP(249.0025,0)`：+0.5 得 249.5025，`%.1F` 得 "249.5"，HALF_DOWN 得 249，应为 250。我没有跑过，需要验证。
- `Trunc::evaluate()`（`Trunc.php:29-64`）是同一次改动里的第三个函数，用 sprintf 加正则截断。
  - `TRUNC(249.9975,0)`：非整数，所以 `$decimals=0`，`sprintf('%.0F')` 得 "250"。
  - 正则 `([.]\d{0})\d+$` 对 "250" 不匹配，所以返回 250，也是错的。
  - 对 digits=0 且小数部分 ≥.5 的值，TRUNC 很可能同样出错。
- 调用点：
  - `Round::down` 只被 `Calculation.php` 的函数表引用。
  - 在 `Writer/Xlsx/Worksheet.php:636-640` 和 `Style/ConditionalFormatting/Wizard/DateValue.php:41-43` 里，ROUNDDOWN 只出现在公式字符串中。
  - 条件格式的日期比较会受影响，但那里的值通常是整数天，影响很小。
- 数组版本经 `evaluateArrayArguments` 走同一函数，改一处即可覆盖。

## 【4 现有测试与约定】
- `tests/PhpSpreadsheetTests/Calculation/Functions/MathTrig/RoundDownTest.php`：
  - 第 15-26 行，`testRoundDown` 用 `assertEqualsWithDelta($expectedResult, $result, 1E-12)`。
  - 第 35-42 行，`testRoundDownArray` 用 delta 1.0e-14。
- 数据文件 `tests/data/Calculation/MathTrig/ROUNDDOWN.php`（37 行）：
  - `[662, '662.79,0']`
  - `[76, '76.9, 0']`
  - `[3.141, '3.14159, 3']`
  - `[31400, '31415.92654,"-2"']`
  - `[-5, 'A5, 0']`（A5 = -5.2）
  - `'negative number and precision' => [-31400, '-31415.92654, -2']`
- 现有用例没有覆盖"小数部分 ≥ .5 且逢 digits 位恰好被 sprintf 进位"的情形。像 `662.79,0` 得 662 能通过，是因为 662.29 的 `%.1F` 是 "662.3"，没有碰到 .5 边界。
- 同样的数据文件结构还有 `ROUNDUP.php`（37 行）和 Trunc 的测试，隐藏测试很可能往这些文件加用例。
- 外部规范是 Excel 语义：ROUNDDOWN 向零截断，负数同样向零（-3.8 得 -3）。
- 题面期望与现有测试和 Excel 语义不冲突。

## 【5 边界与隐含要求】
- 负数：对 -249.9975，digits=0 应得 -249。
- digits 为负：`$digitsPlus1 < 0` 分支单独处理，修复后要保持 `54.1,-1` 得 50、`-31415.92654,-2` 得 -31400。
- digits=-1 时 digitsPlus1=0，走 sprintf 分支，是个边缘情况。
- 非整数 digits：测试里有 `3.2, 0.01`，期望 3，`(int)` 转型保留。
- 浮点表示误差：例如 4.4400、`2.26+2.94` 得 5.20，修复后不能引入 5.19 这类回归。这些正是之前 #1404 的问题。
- 大数或高精度：digits 加整数位数超过 PHP_FLOAT_DIG 时，sprintf 可能不精确。
- 值为 0 的早返回要保留。
- 如果同时修 ROUNDUP 和 TRUNC，要对称处理，且不能破坏现有数据文件。
- 隐藏测试很可能包含 ROUNDDOWN/ROUNDUP/TRUNC 的新边界用例，如 249.9975、负数、digits=0。

## 【6 改动规模】
- 最小修复：只改 `Round.php` 里 `down()` 一个函数，约 15 行，局部修补，不需要新结构。
- 完整修复：同样改 `Round::up()` 和 `Trunc::evaluate()` 的 digits≥0 分支，共 2 个文件、3 个函数。
- 另外在 3 个测试数据文件各加几行。
- 不涉及多层改动，不需要改公共 API。

## 【7 难点一句话】
找到根因不难（sprintf 先舍入再 round 的二次舍入）；难在换一种不会引入浮点误差回归的实现（例如用字符串截断，或带容差的 floor），同时保住 `Round::up` 和 `Trunc` 里对称的边界，以及负 digits 和 `5.20` 这类浮点用例，而且题面只给了一个反例。