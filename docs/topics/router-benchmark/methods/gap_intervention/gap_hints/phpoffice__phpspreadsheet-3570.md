## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 并列/调用点**
1. HLookup.php lookup()（约28-39行）与 VLookup.php lookup()（约27-37行）并列，都调用 LookupBase::validateIndexLookup；题面只提 VLOOKUP，HLOOKUP 的 row_index 传数组很可能有同样问题，应一并核对。
2. LookupBase::validateIndexLookup 的参数类型为 float|int|string，数组先被 is_numeric 拒掉再走 ExcelError::throwError；要确认问题出在校验函数还是 lookup() 更早的参数处理。
3. 两个 lookup() 只在 is_array($lookupValue) 时才走 evaluateArrayArgumentsIgnore（ignore=1，不展开 lookupArray）。查 lookupValue 为标量而 indexNumber 为数组时该走哪条路径，以及 ArrayEnabled/ArrayArgumentProcessor 的约定；“取首值”与“逐元素展开”是两种不同处理，需参考仓库里同类函数的做法。

**B. 边界输入**
1. index 数组首元素不合法：{0,1}、{"a",2}、{1.9,2}；取首值后仍要经过 <1 和非数字校验。
2. index 为单元素数组、嵌套/二维数组，如 {{12,13},{1,2}}；需实际查看数组常量解析后的 PHP 结构。
3. 首值大于列数时仍应返回 #REF!；lookup_value 也是数组时，原有展开行为不应被破坏。

**C. 已有约定/文档/测试**
1. 测试数据在 tests/data/Calculation/LookupRef/VLOOKUP.php、HLOOKUP.php，由 VLookupTest.php、HLookupTest.php 驱动；这两个测试通过单元格引用传 index，也有直接写公式的用例。数组常量情形要用公式字符串走完整解析流程测试，不要只直接调用 lookup()。
2. ArrayEnabled（Calculation/ArrayEnabled.php）、Calculation::$arrayReturnType 以及 Calculation.php 的函数映射决定数组参数是展开还是取首元素；查 LookupRef 下其他函数及 docs 中 array-enabled 说明，核对 VLOOKUP/HLOOKUP 应遵循的约定。
3. validateIndexLookup 的注释记录了 Excel 对非数值 index 的错误行为（VALUE/NUM/REF），改动不能改变这些既有错误结果。

**D. 提交前自测**
1. 公式 =VLOOKUP(A7,range,{2,3,2},FALSE) 实际计算，期望返回第2列的值而非 #VALUE!。
2. HLOOKUP 做同样的数组 row_index 测试，并确认标量 index 与单元格引用的原有用例仍通过。
3. index 数组首元素为 0、负数、文本时的错误结果，以及首值大于列数时的 #REF!。
