# 档案：NETWORKDAYS 被写成 `NETWORK_xlfn.DAYS`

## 【1 题面要点】
- **要求的行为**：写 XLSX 时，`=NETWORKDAYS(A1,B1)` 必须原样输出。现状被改写成 `NETWORK_xlfn.DAYS(`。
- **复现**：只有一行 `$ws->setCellValue($c.($keyrow+2), "=NETWORKDAYS(".$c.$keyrow.",".$c.($keyrow+1).")");`。没有给期望输出的完整文本，也没有测试。
- **根因（题面自己指出）**：「The function addXlfnPrefix is being overly aggressive … the preg_replace is also doing this to the "NETWORKDAYS" by converting it to "NETWORK_xlfn.DAYS" which it either (1) should not do or (2) should do it correctly.」
- **修法建议**：题面只给了一个不可取的临时办法，即注释掉 `. '|days'`。这会让真正的 `DAYS()` 丢掉 `_xlfn.` 前缀，所以不能照搬。
- 题面标明是 Writer 问题，版本 1.28.0。

## 【2 相关代码】
- `src/PhpSpreadsheet/Writer/Xlsx/FunctionPrefix.php:7-154`，常量 `XLFNREGEXP`
  - 是一个超长的函数名交替正则，匹配 `(?:_xlfn\.)?((?:_xlws\.)?(name1|name2|...))\s*\(`。
  - 修饰符是 `/Umui`。
  - 第 83 行的 `days` 前面**没有任何词边界**，所以能匹配 `NETWORKDAYS(` 里的 `DAYS(`。
- `FunctionPrefix.php:165-168`，`addXlfnPrefix`：`preg_replace(XLFNREGEXP, '_xlfn.$1(', ...)`。
- `FunctionPrefix.php:156-160`，`XLWSREGEXP`
  - 它只处理 `filter` 和 `sort`，带有 `(?<!_xlws\.)` 的负向后顾，但前面同样没有词边界。
  - 这是潜在的同类问题，例如某个以 `sort(` 结尾的自定义函数名。
- `FunctionPrefix.php:173-193`，`addXlwsPrefix`、`addFunctionPrefix`、`addFunctionPrefixStripEquals`，是对外入口。
- 调用点在 `Writer/Xlsx/Worksheet.php`：
  - 第 501 行：数据验证的 formula。
  - 第 1210 行：单元格 `f`。
  - 第 1237 行：单元格 `f`。
  - 第 1240 行：单元格 `f`。

## 【3 并列与牵连】
- 同一个缺陷模式在**整个交替列表**里都存在。凡是名字是别的函数名后缀的条目，都可能误伤。例如：
  - `days` ← `NETWORKDAYS`
  - `sec`、`sech`、`cot`、`csc`、`let`、`call`、`phi` 等短名
  - 点号分隔的 `t[.]dist`、`f[.]test`、`var[.]s` 等
- 靠交替顺序（最左匹配）可以让 `IMSECH`、`SUMIFS` 这类侥幸正确。只有"后缀恰好是另一个函数"的情形会出错，`NETWORKDAYS` 是最明显的一个。
- `XLWSREGEXP` 是并列的第二个正则，也缺词边界，应一并处理。
- 改正则会影响所有写出路径（单元格公式、数组公式、数据验证）和条件格式。`XlfnFunctionsTest.php:93-94` 断言条件格式里有 `_xlfn.ISOWEEKNUM`。
- 读取侧不用改。`Calculation.php:34` 的 `CALCULATION_REGEXP_FUNCTION` 已经用 `(?:_xlfn\.)?(?:_xlws\.)?` 解析前缀，并且 `src` 里没有别处处理 `_xlfn`。

## 【4 现有测试与约定】
- `tests/PhpSpreadsheetTests/Writer/Xlsx/FunctionPrefixTest.php:22-29` 的 data provider：
  - `'Basic Legacy Function' => ['SUM()', 'SUM()']`
  - `'New Function without Prefix' => ['_xlfn.ARABIC()', 'ARABIC()']`
  - `'New Function already Prefixed' => ['_xlfn.ARABIC()', '_xlfn.ARABIC()']`
  - `'New Function requiring Double-Prefix' => ['_xlfn._xlws.FILTER()', 'FILTER()']`
  - `'... already partially Prefixed' => ['_xlfn._xlws.FILTER()', '_xlfn.FILTER()']`，另有 `'_xlws.FILTER()'` 和 `'_xlfn._xlws.FILTER()'` 两种输入，期望相同。
  - `'Multiple Functions' => ['_xlfn._xlws.SORT(_xlfn._xlws.FILTER(A:A, A:A<>""))', 'SORT(FILTER(A:A, A:A<>""))']`
- 没有 NETWORKDAYS 或 DAYS 的用例。隐藏测试很可能是在这个 provider 里新增，例如 `NETWORKDAYS()` 保持原样，以及 `DAYS()` → `_xlfn.DAYS()`。
- `testFunctionPrefixWithEquals` 被注释掉了。
- `XlfnFunctionsTest.php:17-31` 做读写往返，断言写出的是 `=_xlfn.MODE.SNGL(...)`、`=_xlfn.ISOWEEKNUM(A3)+WEEKNUM(A4)+_xlfn.ISOWEEKNUM(A5)` 等。
- `ArrayFormulaPrefixTest.php:48` 断言 `_xlfn.TEXTJOIN(...IF(ISNUMBER(...` 里嵌套的内层函数不加前缀。
- 外部规范是 ECMA/Excel 的 `_xlfn.` 约定：只有 `DAYS` 本身需要前缀，`NETWORKDAYS` 不需要，`NETWORKDAYS.INTL` 在列表第 40 行是需要前缀的。这与题面期望没有冲突。

## 【5 边界与隐含要求】
- `DAYS(` 仍要加前缀，`DAYS360(` 本来就不匹配，因为后面没有 `(`。
- `NETWORKDAYS.INTL(` 必须仍得到 `_xlfn.NETWORKDAYS.INTL(`。
- 要把"前缀已存在"的幂等性（`_xlfn.`、`_xlws.`、`_xlfn._xlws.` 三种输入）和词边界同时处理好。
  - 简单加 `\b` 会有问题：`_xlfn.DAYS` 中 `.` 与 `D` 之间也是边界，而 `NETWORK` 与 `DAYS` 之间不是，所以 `\b` 能区分这两种情形。
  - 点号函数名（如 `T.DIST`）左边不能被误当成词内部。
  - 含点号的函数名前面如果是 `.` 或字母，需要决定是否算边界。
- 公式里字符串字面量内的文本（如 `"days("`）理论上也会被替换，但这不是本题范围。
- 大小写不敏感：`/i` 修饰符要保持，小写 `networkdays(` 同样不能被改写。
- 前面是 `+`、`(`、`,`、空格、`=` 的情况都要继续命中，例如 `1+DAYS(...)`。
- 同一公式里同时有 `NETWORKDAYS(` 和 `DAYS(` 时，只有后者被加前缀。

## 【6 改动规模】
- 只改 1 个源文件、1 处正则，`FunctionPrefix.php`。
- 最小改法是给 `XLFNREGEXP` 前面加一个后顾或词边界，比如 `(?<![\p{L}\p{N}_.])` 之类，同时可以顺手改 `XLWSREGEXP`。
- 再往 `FunctionPrefixTest.php` 里补用例。
- 是局部修补，不需要新增结构，也不涉及调用点。

## 【7 难点一句话】
难点不在定位（根因题面已经点明）：它在于写一个既挡住 `NETWORKDAYS` 这类"后缀撞名"，又不破坏已有 `_xlfn.`/`_xlws.` 前缀的幂等处理、点号函数名（`T.DIST`、`NETWORKDAYS.INTL`）和 `/Umui` 修饰符下行为的边界断言，所以整体偏简单。