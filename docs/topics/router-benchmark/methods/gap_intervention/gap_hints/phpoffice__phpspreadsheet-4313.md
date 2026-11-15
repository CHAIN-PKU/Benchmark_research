## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) FormulaTranslator::convertToExcelFormulaValue 的正则同样用 [^\.]+ 匹配表名，带点的表名在公式 [$'a.b'.A1:.A2] 里很可能同样出错。2) convertToExcelAddressValue 有 3 个调用点：Ods/AutoFilter.php:23、DefinedNames.php:29-30、DefinedNames.php:48，都要核对输入。3) AutoFilter.php 把转换结果直接交给 setAutoFilter，要确认带引号表名的处理。4) 题面例子的起止两个表名相同，现有第一条正则丢弃第二个表名，要看清楚。
B. 带引号但无点的表名、不带引号的普通表名（不能改坏）；多个点的表名；转义单引号的表名；带 $ 的绝对引用；单个单元格、无表名的 .A1:.B2；起止表名不同的 3-D 范围。
C. tests 目录里没有 convertToExcel/FormulaTranslator 的直接单元测试，要找 Ods 读取的测试和样例；现有正则带 /miu，数组形式依次替换，顺序有依赖；参考其他地方引用带引号表名的格式 'Sheet name'!A1。
D. 1) 题面用例 'test.bug'.A1:'test.bug'.A2 期望 'test.bug'!A1:A2。2) 同表名放进公式 [$'test.bug'.A1:.A2] 和 [$'test.bug'.A1]。3) 回归：Sheet1.A1:B2、$Sheet1.$A$1、.A1:.B2、.A1 转换结果不变，并跑现有 Ods 读取测试。
