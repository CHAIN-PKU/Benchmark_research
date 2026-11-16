**档案：VLOOKUP 的 index_number 传入数组（如 `{12,13,12}`）返回 #VALUE!**

我共做了约 6 次搜索和阅读，没有运行代码。

**【1 题面要点】**
- 公式为 `VLOOKUP(A7,Sheet2!$A$1:$AG$50,{12,13,12},FALSE)`。
- 期望行为："Return the data in the 12th column matched by Sheet2!$A$1:$AG$50"。
- 实际行为是 `#VALUE!`。
- 题面没有可用的复现代码，PHP 代码块只有 `$spreadsheet->getActiveSheet()->toArray();`，也没有给期望输出。
- 修法建议是最后一句："The parameter index_number of the function validateIndexLookup failed to be validated. The current parameter is [12, 13, 12], then only the first value in the array should be taken"。
- 题面自相矛盾：Excel 对数组常量的真实行为是溢出为多值数组，而题面只要求取第一个值。
- 题面指出的出错位置是 `LookupBase::validateIndexLookup`，对应版本是 1.28.0。

**【2 相关代码】**
- `src/PhpSpreadsheet/Calculation/LookupRef/LookupBase.php:21` 的 `validateIndexLookup(array $lookup_array, $index_number): int` 是主因。
  - 它先做 `is_numeric($index_number)`，数组会不通过。
  - 随后 `ExcelError::throwError($index_number)` 把数组转成 #VALUE!。
  - 方法的 docblock 写的是 `float|int|string`，没有数组类型。
- `LookupRef/VLookup.php:25-41` 的 `lookup()`：
  - 第 29 行只在 `$lookupValue` 是数组时才走 `evaluateArrayArgumentsIgnore`，第 30 行是这个调用本身。
  - 第 37 行调用 `validateIndexLookup`。
  - `$indexNumber` 是数组时没有任何处理。
- `LookupRef/HLookup.php:28-61` 的 `lookup()` 结构相同，第 39 行同样调用 `validateIndexLookup`。
- `Calculation/ArrayEnabled.php:120` 的 `evaluateArrayArgumentsIgnore` 把第 `$ignore` 个参数（lookupArray）占位后做数组展开。它只在 `$lookupValue` 为数组时才会触发，对 `$indexNumber` 为数组的情况不起作用。
- `Calculation/Calculation.php:2785` 把 VLOOKUP 注册到 `VLookup::lookup`，`argumentCount` 为 '3,4'。

**【3 并列与牵连】**
- HLOOKUP 与 VLOOKUP 共用 `validateIndexLookup`，所以同一个缺陷在 HLookup 里也存在，需要一并处理。
- `validateIndexLookup` 只被这两处调用（grep 确认）。把数组处理放进这个共用方法，两个函数会一起修好。
- 如果改成在 `lookup()` 入口处理，需要改两处。
- `ExcelMatch.php:38` 的 MATCH 也用 `evaluateArrayArgumentsIgnore`，但它不调用 `validateIndexLookup`，不受影响。
- `LOOKUP`（`Lookup.php`）和 INDEX 没有查看，不确定是否相关。

**【4 现有测试与约定】**
- `tests/PhpSpreadsheetTests/Calculation/Functions/LookupRef/VLookupTest.php:12-40` 的 `testVLOOKUP` 把 index 写进单元格 Z97，用公式 `=VLOOKUP(Z98,$dimension,Z97$lastarg)` 计算，并用 `assertEquals($expectedResult, $result)` 断言。
- 数据在 `tests/data/Calculation/LookupRef/VLOOKUP.php`。其中第 94、177 行的 `'#VALUE!'` 是 index 非法（小于 1 或字符串字面量）时的期望，修复后必须保持。
- 第 52-59 行的 `testVLookupArray` 断言：lookupValue 是数组 `{"Orange","Green","Red"}`、index 为标量 `'2'` 时，期望 `[[4.19, 5.77, 4.14]]`。
  - 这说明仓库对 lookupValue 数组的约定是展开成数组结果。
  - 与题面"取第一个值"的做法可能存在张力。
- `HLookupTest.php` 存在，没有读。
- `LookupBase.php:23-27` 的注释说明："Excel results are inconsistent when index is non-numeric"，现有逻辑是"尽力而为"。
- 外部规范是 Excel 的数组公式语义，没有仓库内的参考实现。
- 隐藏测试很可能新增一个数组 index 的用例，期望值可能是单值或数组，无法从题面判断。

**【5 边界与隐含要求】**
- 数组形态：行内数组常量解析后可能是 `[[12,13,12]]`（嵌套），也可能是一维 `[12,13,12]`，需要先确认实际形态再取首元素，否则 `is_numeric` 仍会失败。
- 空数组：需要决定返回什么错误。
- 数组首元素不是数字时，应沿用原有的 `throwError` 路径。
- 数组首元素小于 1 时，应返回 #VALUE!。
- lookupValue 与 index 同时为数组时，现有展开逻辑不会处理 index。
- `evaluateArrayArgumentsIgnore` 只展开 lookupValue，需要确认不会破坏它。
- 取值后 `(int)` 转换，以及单元格引用到区间的情况。
- HLOOKUP 要同步，且题面只提到 VLOOKUP。
- 如果期望是真正的数组结果，改动会大得多，需要对 index 做数组展开，并保持 lookupArray 不被展开。

**【6 改动规模】**
- 最小方案是只改 `LookupBase.php` 的一处，约 3 到 6 行。在 `validateIndexLookup` 里，如果 `$index_number` 是数组就递归取首元素，同时调整参数类型注解。
- 这会同时修好 VLOOKUP 和 HLOOKUP。
- 如果要做完整数组展开，需要改 `VLookup.php` 和 `HLookup.php` 各一处，并适配 `ArrayEnabled` 的忽略参数机制。
- 无论哪种方案，都要补测试数据。
- 总体是局部修补，不需要新结构。

**【7 难点一句话】**
代码定位很容易，难点在于判断期望结果：题面说"取第一个值"，而 Excel 真实行为和仓库对 lookupValue 数组的约定都是返回数组。隐藏测试到底期望标量还是数组，题面不能确定，还要确认数组在这里的实际嵌套形态。