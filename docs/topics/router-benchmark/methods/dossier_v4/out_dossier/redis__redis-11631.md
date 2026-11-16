**档案：fixedpoint_d2string 小数部分补零循环错误（GEORADIUS WITHDIST 距离乱码）**

说明：本档案基于对 `src/util.c`、`src/geo.c`、`tests/unit/geo.tcl` 的阅读。检索共 5 次，不足 10 次。其中调用点和测试只做了 grep，没有读到上下文，也没有搜 `tests/` 下其他位置。下面列出的结论都来自这几处。

**【1 题面要点】**
- 要求的行为：`GEORADIUS ... WITHDIST` 返回的距离应是合法的定点字符串。
- 题面期望值是 `[[b'1', 0.0001]]`，实际得到 `b'0.00\xfc1'`，其中夹着一个非法字节。
- 复现步骤：用 geoadd 加 4 个点，调用 WITHDIST，重复多次后才出现。
- 题面原话：“The second item in each array should be a float but it is a partially mangled binary value”。
- 题面没有给修法建议。
- 题面把问题定位到 7.0.6 升级之后，没有指出具体代码。
- “多次调用后才出现”暗示读到了未初始化的栈内存：`dbuf` 是栈上 `char[128]`，没有初始化。

**【2 相关代码】**
- `src/util.c:650` `fixedpoint_d2string(dst, dstlen, dvalue, fractional_digits)`：把 double 转成固定小数位的字符串，7.0.6 新增的优化版 `%.Nf`。
- `src/util.c:704-713`：这是 bug 所在，我读代码得出的判断。
  - 当 `integer_digits < 1` 时，代码写入 `dst[0]='0'`，并令 `integer_digits=1`。
  - 随后 `dst[1]='.'`，`size = 1+1+fractional_digits`。
  - 补零循环是 `for (i = integer_digits+1; i < fractional_digits; i++) dst[i]='0';`，终止条件错了。
  - 以 `0.0001`、4 位小数为例：`value=1`，`ndigits=1`，`size=6`。循环只写 `dst[2]`、`dst[3]`，而 `dst[4]` 没写。
  - 后面 `dst[next=5]='1'`，所以结果是 `0.00?1`，`?` 是未初始化字节，与题面的 `0.00\xfc1` 吻合。
  - 正确的补零范围应是：从小数点后第一位，一直补到有效数字之前。也就是 `integer_digits+1` 到 `size - ndigits` 之间的位置。
  - 简单做法：循环终止条件改成 `i < size - ndigits`，或直接按补零个数计算。
- `src/util.c:715-734`：从尾部往前写数字，并跳过小数点位置（`next == integer_digits` 时 `next--`）。
- `src/geo.c:212` `addReplyDoubleDistance`：用 `fixedpoint_d2string(dbuf,128,d,4)`，再 `addReplyBulkCBuffer`。
- `src/geo.c:792`、`geo.c:1003`：调用点，分别在 GEORADIUS/GEOSEARCH 回复和 GEODIST 里。

**【3 并列与牵连】**
- `fixedpoint_d2string` 全仓库只有 `geo.c:214` 一处调用，所以影响面是所有带距离输出的 geo 命令：GEORADIUS、GEORADIUSBYMEMBER、GEOSEARCH、GEODIST。
- 我没有读 `geo.c:1003` 的上下文，这里按行号推断是 GEODIST。
- 没有发现并列的同类实现需要同步改。
- `util.c:1274` 里的内置单测同样要补用例，但这不是并列实现。

**【4 现有测试与约定】**
- `src/util.c:1274-1319` 的 `test_fixedpoint_d2string` 现有断言：
  - `0.0 → "0.0000"`
  - `0.01 → "0.0100"`
  - `-0.01 → "-0.0100"`
  - `0.01` 配 17 位 → `"0.01000000000000000"`
  - `10.01 → "10.0100"`
  - 负例：18 位、0 位、`dstlen=1` 均返回 0。
- 这些用例没覆盖“有效数字比小数位数少 2 位及以上”的情况，比如 `0.0001`，所以没暴露 bug。
- `0.01` 配 4 位时 `value=100`，`ndigits=3`，循环 `i=2; i<4` 写 `dst[2]`、`dst[3]`，碰巧补对了。
- `tests/unit/geo.tcl:254-259, 358` 有 WITHDIST 测试。我只 grep 到了行，没有读断言内容，也没看到有极小距离的用例。
- 约定是函数注释写明“optimized version of snprintf "%.<fractional_digits>f"”，所以正确性标准就是与 `%.Nf` 输出一致。
- 与题面期望不冲突。

**【5 边界与隐含要求】**
- 所有 `ndigits <= fractional_digits-2` 的值，即前导零不止一个的小数：`0.0001`、`0.0012`、`0.00001` 配 4 位（四舍五入后）。
- 四舍五入后变成 0 的值，比如 `0.00001` 配 4 位。此时 `svalue=0`，`digits10(0)` 的返回需要核实（我没读到 `digits10` 对 0 的处理）。更稳妥的修法是先判断 `svalue==0`。
- 负数的前导零情况：`-0.0001`，此时 `dst` 已经前移了 1 位。
- 大数值时 `ndigits >= dstlen` 的检查。
- 隐含要求：输出必须以 `\0` 结尾，长度必须正确。
- 其他小数位数（1 到 17）下不能引入新的越界写入。

**【6 改动规模】**
- 核心修复：1 个文件（`src/util.c`）1 处，改补零循环的边界，一两行。
- 测试：在 `util.c` 的 `test_fixedpoint_d2string` 补几条用例，也可能在 `tests/unit/geo.tcl` 补一个小距离的 WITHDIST 用例。
- 局部修补，不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
- 难点主要不在改代码，而在定位：症状出在 geo 命令上，根因却是 `fixedpoint_d2string` 补零循环的终止条件写错，而且只在有多个前导零的小数上才触发。同时还要注意隐藏测试很可能直接断言边界输出，比如 `0.0001` 配 4 位，以及舍入为 0 的情况。