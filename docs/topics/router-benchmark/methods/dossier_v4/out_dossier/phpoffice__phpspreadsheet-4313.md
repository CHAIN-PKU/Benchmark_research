# 仓库档案：ODS 带点工作表名 + 自动筛选

## 【1 题面要点】
- 期望：ODS 地址 `'test.bug'.A1:'test.bug'.A2` 转成 `'test.bug'!A1:A2`。
- 实际：得到 `'test!bug'!A1:bug'A2`，随后抛出 "Invalid cell coordinate BUG'A2"。
- 复现：只给了一个 `bugtest.ods` 附件，没有测试代码。给的 PHP 代码只是 `IOFactory::createReaderForFile(...)->load()`。
- 修法建议（原句）："the error is in one of the Ods\FormulaTranslator method "convertToExcelRange". One of the regular expressions need to be modified to match the single-quote escaped notation with dots."
- 说明：issue 里的方法名是旧名，当前方法是 `convertToExcelAddressValue`。issue 没有给出期望输出之外的预期，如无引号、含 `$`、含空格的情形。

## 【2 相关代码】
- `src/PhpSpreadsheet/Reader/Ods/FormulaTranslator.php:9-35`，`convertToExcelAddressValue`。这是主犯。
  - 5 条正则都用 `[^\.]+` 来切分"工作表名.单元格"，所以工作表名里的点会被当成分隔符（第 18-22 行）。
  - 前 3 条按位置依次处理：3-d 范围 `$1.$2:$3.$4`，另一张表的范围 `$1.$2:.$3`，另一张表的单元格 `$1.$2`。
  - 后 2 条处理无表名的范围和单元格 `.A1:.B2`、`.A1`。
  - 替换后都不保留或重新补引号，只靠原串自带的引号。
- `src/PhpSpreadsheet/Reader/Ods/FormulaTranslator.php:37-96`，`convertToExcelFormulaValue`。
  - 公式转换，同样用 `[^\.]+` 的正则，但要求 `[...]` 包裹（第 51-54 行）。
  - 同类的带点工作表名问题也在这里，如 `['a.b'.A1]`。
  - 题面没提，但同源。
- `src/PhpSpreadsheet/Reader/Ods/AutoFilter.php:21-24`，读 `table:target-range-address`，调用 `convertToExcelAddressValue` 后传给 `Worksheet::setAutoFilter`。这是本题的触发点。
- `src/PhpSpreadsheet/Reader/Ods/DefinedNames.php:29-30, 48`，另外 3 个调用点。
  - 命名范围的 `base-cell-address`、`cell-range-address`，以及命名表达式的 `base-cell-address`。
  - `addDefinedName` 第 63 行用 `Worksheet::extractSheetTitle($baseAddress, true)` 取工作表名，再 `getSheetByName`。
- `src/PhpSpreadsheet/Worksheet/Worksheet.php:1962-1967`，`setAutoFilter` 先 `Validations::validateCellRange`，再 `Functions::trimSheetFromCellReference`。这里是报错的发生点。
- `src/PhpSpreadsheet/Worksheet/AutoFilter.php:110-115`，`setRange` 用 `Worksheet::extractSheetTitle`（`Worksheet.php:3185`，取最后一个 `!` 之后的部分）去掉表名。

## 【3 并列与牵连】
- 同一个转换函数被 3 个调用点用，调用点本身不需要改，改函数即可。
  - AutoFilter.php:23。
  - DefinedNames.php:29-30、48。
- 并列实现：`convertToExcelFormulaValue` 里 4 条结构相同的正则（第 51-54 行）也有同样的缺陷。
  - 它在 `Reader/Ods.php:603` 和 `DefinedNames.php:50` 被调用。
  - 题面只要求 `convertToExcelAddressValue`，但维护者的修复可能顺带处理公式。
  - 隐藏测试多半只测地址函数或 AutoFilter 读取，公式是否被测不确定。
- 影响面：命名范围、命名表达式的 base address 也经过同一函数。
  - 改正则后，这些的行为也会变，要保证既有 `DefinedNames.ods` 不回归。
- 其他 Reader 目录下没有找到同类的 `[^\.]+` 写法。该模式只在 Ods 的 FormulaTranslator 里。

## 【4 现有测试与约定】
- `tests/PhpSpreadsheetTests/Reader/Ods/AutoFilterTest.php:21`：`self::assertSame('A1:C9', $autoFilterRange);`，数据文件 `tests/data/Reader/Ods/AutoFilter.ods`。
  - 只有这一个自动筛选测试，且用的是无引号、不含点的表名。
  - 题面期望的 `'test.bug'!A1:A2` 与此不冲突。
- 没有直接针对 `FormulaTranslator` 的单元测试（在 tests 下搜 `FormulaTranslator|convertToExcel` 无结果）。
  - 隐藏测试很可能是新增 `.ods` 数据文件（类似 `tests/data/Reader/Ods/issue.xxxx.ods`）加读取断言。
  - 也可能是直接对 `convertToExcelAddressValue` 做数据驱动断言。
  - 新增 `.ods` 文件需要测试方自备。
- 约定：ODS 地址格式（OpenFormula）是 `$'Sheet.Name'.A1` 或 `Sheet.A1`，表名带特殊字符时用单引号，引号内的单引号写成 `''`。仓库里没有规范文档，只有 `Worksheet::extractSheetTitle` 约定"取最后一个 `!`"。
- 现有测试数据没有出现带点工作表名，所以不存在与题面冲突的既有断言。

## 【5 边界与隐含要求】
- 工作表名带引号且带点：`'a.b'.A1`、`$'a.b'.A1:.B2`，以及 3-d 形式 `'a.b'.A1:'a.b'.A2`（题面例子）。
- 带点又带 `$` 绝对引用的地址，如 `$'test.bug'.$A$1`。工作表名前的 `$` 要保留原有的处理（当前是被正则吞掉）。
- 工作表名里有 `''` 转义的单引号。
- 无引号的工作表名（`Sheet1.A1`）、无表名（`.A1:.B2`）要继续走老路径。
- 范围两端工作表名不同的 3-d 引用：现有代码假设相同，取 `$4`，保持行为。
- 单元格引用里本身不含点，所以"引号内的点"与"分隔点"可以靠引号区分。
- 结果传入 `setAutoFilter` 后，`extractSheetTitle` 用的是最后一个 `!`。表名里含 `!` 时仍有隐患，但题面未涉及。
- 公式里 `[` `]` 包裹的引用若带点表名，同类处理（见第 3 项）。
- 加载 `loadSheetsOnly` 时 `getSheetByName` 可能返回 null，`DefinedNames` 已有处理。

## 【6 改动规模】
- 最小修复：1 个文件（`FormulaTranslator.php`），重写或补充 `convertToExcelAddressValue` 的 5 条正则，或改为先匹配引号段再替换。
- 完整一点：同文件里的 `convertToExcelFormulaValue` 也改。
- 属于局部修补，不涉及新结构，也不贯穿多层。
- 测试要新增：1 个 `.ods` 数据文件加 1 个测试用例。

## 【7 难点一句话】
难点在于 `convertToExcelAddressValue` 的 5 条正则按顺序依次匹配，并且彼此重叠，要在不破坏无引号表名、无表名、`$` 前缀、3-d 范围这些既有路径的前提下，让"带引号、含点的表名"整体作为一个单元参与匹配。题面没给其他示例，边界要自己推。