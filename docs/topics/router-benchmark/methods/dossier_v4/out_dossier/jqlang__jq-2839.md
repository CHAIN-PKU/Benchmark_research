# 档案：jq `jv_cmp()` 比较两个 decNumber 字面量时崩溃

我没有编译或运行复现。下面的结论来自读代码，复现时的行为是根据 issue 的栈回溯和代码推断的。

## 【1 题面要点】
- 要求：`3E506760210 < 63E-6855002263` 和 `[3E506760210, 63E-6855002263] | sort` 不能崩溃，也不能触发 UB。
- 题面没给期望输出，也没给修法建议。
- 题面给了两条完整的复现命令和 ASAN 栈回溯。
- 关键报错：`decNumber.c:6209: signed integer overflow: 506760210 - -1999999996`，随后是 `decUnitCompare` 里的 `index -1788207090 out of bounds`。
- 两个调用路径：
  - 常量折叠：`binop_less` → `order_cmp` → `jv_cmp`。
  - 排序：`sort_cmp` → `jv_cmp`。
- 题面说同一个 oss-fuzz 报告已因"常量折叠不再对加法调用 `jv_cmp`"而显示为已修复，但根因还在。

## 【2 相关代码】
- `src/jv.c:744-773` `jvp_number_cmp`：
  - 两边都是字面量（`JVP_FLAGS_NUMBER_LITERAL`）时，直接调用 `decNumberCompare(&res, a, b, DEC_CONTEXT())`，再按 res 的零、负、正返回 0、-1、1。
  - 这里没有任何防护，是最可能的修复点。
  - 否则回退到 double 比较。
- `src/decNumber/decNumber.c:6209` `decCompare`：
  - 当 `lhs->exponent > rhs->exponent` 时先交换两边。
  - 然后调用 `decUnitCompare(..., rhs->exponent-lhs->exponent)`。
  - 这个 `Int` 减法在两个指数相差很大时会溢出。
  - 这里 `exp` 是溢出后的负数，而 `decUnitCompare`（约 6235-6262 行）假定 `exp>=0`。
  - 它在 6257 行用 `exp` 算出的下标访问 `accbuff` 数组，导致越界读。
- `src/jv.c:530-532`：
  - 通用 decimal 上下文用 `DEC_INIT_BASE`，`digits = DEC_MAX_DIGITS-1`，`emax` 约为 ±999999999。
  - 63E-6855002263 的指数被钳到约 -1999999996，这和报错里的数一致。
  - 相差约 2.5e9，超过 int 范围 2^31-1（约 2.147e9）。
- `src/jv_aux.c:559-569` `jv_cmp` 的 NUMBER 分支：先处理 NaN，再调用 `jvp_number_cmp`。
- `src/jv.c:775` `jvp_number_equal`：`jvp_number_cmp(a,b)==0`，`jv_equal` 在 `jv.c:1922` 调用它。

## 【3 并列与牵连】
- 所有走 `jvp_number_cmp` 的路径都受影响：
  - `jv_cmp`：`<`、`>`、`sort`、`sort_by`、`group_by`、`unique`、`min` 和 `max`。
  - `jv_equal`：`==`，以及 `index`、`indices` 和 `unique`。
  - `jv_aux.c` 里对象 key 之外的排序。
- 需要核对：`jv_equal` / `jv_identical` 的数字分支是否走同一个函数。`jv.c:1922` 看起来是，所以修 `jvp_number_cmp` 一处就能覆盖。
- 常量折叠（`parser.y:221`）只是触发点，不是病根。
- 其他 decNumber 运算（加减乘除）在本档案里没有核对是否存在同类溢出，应该不需要改。
- 如果改 decNumber 第三方源码里的 `decCompare`，会改动随仓库附带的 `src/decNumber/`。

## 【4 现有测试与约定】
- `tests/jq.test:559`：`5E500000000>5E-5000000000` → `true`。
  - 这是上一次相关修复加的回归用例。
  - 它说明期望的语义是"按数学值比较"，大指数的数不能因为溢出被当成 NaN 或出错。
  - 这个例子的指数差约 5.5e9，也会溢出 int，但没崩溃，可能只是运气。具体原因我没查。
- `tests/shtest:179`：`1E9999999999` 的回归测试（#2367）。
- `src/jv.c:629-636`：字面量转 double 时对 NaN 和无穷的处理方式，可以参考。
- 与题面不冲突：题面只要求不崩溃，正确结果隐含是数学上的大小关系。
- 隐藏测试很可能是在 `tests/jq.test` 里加类似 `3E506760210 < 63E-6855002263` → `false` 的用例，可能还有 sort 用例。

## 【5 边界与隐含要求】
- 正确结果应是 `3E506760210 > 63E-6855002263`，因为前者约 3e506760210，后者约 6.3e-6855002262。
  - 所以 `<` 为 false，sort 为 `[63E-6855002263, 3E506760210]`。
  - 输出形式也要注意：排序后的字面量如何打印（保留原字面量还是转 double）。
- 符号组合：正对负、负对负，以及指数差大到溢出的两个方向（lhs 指数大或 rhs 指数大）。
- 零、无穷、NaN 的组合：
  - 零和无穷在 decCompare 前半段已经处理。
  - 但"符号相同、指数差溢出"的情形必须覆盖。
- 两边位数很多（`digits` 很大）时，`decUnitCompare` 里的缓冲区分配逻辑是否也有风险，需要确认。
- 一边是字面量、一边是普通 double 时走 double 比较，不受影响。
- 如果用"先比较调整后指数（adjusted exponent）"的办法，要避免自己再引入溢出，用 int64 或先比较符号。

## 【6 改动规模】
- 最小修法是局部修补：只改 `src/jv.c` 的 `jvp_number_cmp` 一个函数，在调用 `decNumberCompare` 前增加指数差过大的快速判定。
- 另一种修法是改 `decNumber.c` 的 `decCompare` 里一处减法。
- 测试方面是在 `tests/jq.test` 加 1-2 个用例。
- 不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
难点不在改动量，而在判断修法放在哪一层、怎么保证数学结果正确（特别是指数差溢出时的大小判定，以及符号、零、无穷的组合），而不是简单地防崩溃。