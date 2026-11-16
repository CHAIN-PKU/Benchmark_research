**仓库档案：fmt 浮点本地化（`L`）宽度对齐问题**

说明：本档案只靠读代码得出，没有编译，也没有运行复现。下面第 2、3 节的行号来自 `include/fmt/format.h`。

**【1 题面要点】**
- 要求的行为：`{:19.3Lf}` 在带千位分隔的本地化下，输出宽度必须恰好是 19。
- 题面给了完整复现，只有一个例子是错的：`fmt::print("    VZ = {:19.3Lf}\n", 0.295)`。
- 题面给的期望：把 0.295 换成 `1.295` 后对齐正确，去掉 `L` 也正确。对齐正确指的是：每行数值占满 19 列，右对齐。
- 题面给的错误输出：`VZ =               0.295`。其中 0.295 前有 15 个空格，总宽 20，比其他行多 1 列。
- 题面没有给修法建议，也没有给期望输出的原文。
- 题面标题说"整数部分为零"才出错。

**【2 相关代码】**
- `format.h:2562` 的 `do_write_float` 负责计算 `size` 并调用 `write_padded<align::right>`。
  - 它按 `f.exponent` 和 `exp = f.exponent + significand_size` 分三条分支：
    - 2615 起：`exponent >= 0`，整数加补零。
    - 2635 起：`exp > 0`，形如 `12.34`。
    - 2648–2663：`exp <= 0`，形如 `0.001234`。
  - 前两条分支各自构造 `Grouping(loc, fspecs.locale)`，并把 `count_separators(...)` 加进 `size`。
  - 第三条分支（0.295 走的就是它）完全没有 grouping，`size = digits + 1(0) + 1(点) + num_zeros`，写出的内容也没有任何分隔符。
- 嫌疑点在第二条分支的 2640 行：`grouping.count_separators(significand_size)` 传的是有效数字个数，不是整数部分位数 `exp`。
  - 对 `5.980`（有效数字 `5980`，`exp` 为 1），`count_separators(4)` 会得到 1，但整数部分只有 1 位，不该有分隔符。
  - `count_separators` 的实现在 2082 行：`while (num_digits > next(state)) ++count`。
  - 实际写出时用的是 `write_significand(..., exp, ...)`，也就是 2554 行只对前 `integral_size` 位做分组。
  - 所以 `size` 与实际写出不一致。我认为这是最可能的根因之一。
  - 对照第一条分支：2626 行传的是 `exp`，是对的。
  - 注意：这与题面现象不完全吻合。题面说 `1.295` 正常、`0.295` 异常，按这个推理两者都会偏。我没法确认具体是哪一行，需要实际跑一遍。
- `format.h:2542–2558` 的带 grouping 版 `write_significand`：
  - 它对 `buffer` 前 `integral_size` 位调用 `grouping.apply(out, ...)`。
  - 但 2554 行 `grouping.apply(...)` 的返回值被丢掉了，之后继续写 `out`。如果 `apply` 的输出迭代器是按值传递的，会有问题。这个要在实现层面核实。
- `format.h:2049–2112` 的 `digit_grouping`：
  - `count_separators`（2082）和 `apply`（2091）是一对，必须保持一致。
  - `apply` 里 `if (i >= num_digits) break;` 的边界，与 `count_separators` 的 `num_digits > next(state)` 的边界要对得上。
- `format.h:3710–3756` 的 `write_float(out, T value, ...)` 把 `fspecs.locale` 传下去，最后调 `write_float(out, f, specs, fspecs, loc)`（2681）。
- `format.h:3758–3766` 的 `write` 对浮点先尝试 `write_loc`。
  - `loc_writer::operator()`（2185–2188）对非整数直接返回 false，所以浮点其实走 `do_write_float`，不走 locale 的 `num_put`。
- `format.h:1770` 的 `write_padded` 只按传入的 `size` 算填充，所以 `size` 错 1 就会直接错位 1 列。

**【3 并列与牵连】**
- 并列实现：`do_write_float` 里三条分支各有一套 `size` 计算，必须逐条核对。
  - 指数格式分支（2586–2612）没有 grouping，不受影响。
  - 本题涉及 2625–2626、2639–2640 和第三条分支。
- `fallback_digit_grouping`（2666–2678）是 constexpr 路径用的空实现，接口要与 `digit_grouping` 保持一致。
  - 如果给 `digit_grouping` 新增方法，这里也要加。
- `write_int` 的 grouping 版本（2114–2133）用同一个 `digit_grouping`。改 `count_separators` 或 `apply` 会影响整数 `{:L}`。
- `loc_writer` 里的 `decimal_point` 成员（2175）对浮点没用上，这是历史遗留，不用动。
- `include/fmt/xchar.h` 和 `format.h` 的 `wchar_t` 实例会同样受影响，因为是模板。

**【4 现有测试与约定】**
- `test/xchar-test.cc:435–440` 的 locale 浮点测试：
  - `EXPECT_EQ(fmt::format(loc, "{:L}", 1.23), "1?23")`
  - `EXPECT_EQ(fmt::format(loc, "{:Lf}", 1.23), "1?230000")`
  - `EXPECT_EQ(fmt::format(loc, "{:L}", 1234.5), "1~234?5")`
  - `EXPECT_EQ(fmt::format(loc, "{:8L}", 1230.0), "   1~230")`
- 现有测试里没有带宽度、带千位分隔、整数部分为 0 的浮点用例。
- `test/format-test.cc:1340` 是 `EXPECT_EQ(fmt::format("{:L}", 42.0), "42")`，在 C 区域下没有分隔。
- 约定：本地化行为应等价于 C++ `std::printf` 加 `'` 标志、或 `std::num_put`。宽度语义是输出总宽度恰好为指定值。
- 与题面期望没有冲突。
- 隐藏测试很可能放在 `test/xchar-test.cc` 的 `numpunct` 区域（带宽度的 `Lf`），测的是 `"{:Lf}"` 等对齐。

**【5 边界与隐含要求】**
- 负数（有符号）：`sign` 已计入 `size`（2570），但要确认对齐不受影响。
- 整数部分刚好 3 位、4 位、6 位等恰好跨千位边界的值。例如 `1234.5`、`999.9`。
- 整数部分为 0 且有补零，如 `0.001` 配 `{:.3Lf}`，或 `{:.2Lf}` 配 `0.001`（有效数字为 0）。
- 非固定格式（`{:L}`、`{:Lg}`）和 `showpoint`（`#`）。
- 指数大于等于 0 的分支（`12000.0` 之类）也要确认 `count_separators(exp)` 对。
- `wchar_t`（`xchar.h`）的同一路径。
- 自定义 grouping（如 `"\1\2\3"`）和 `grouping_` 以 0 或 `max_value<char>` 结尾的情况（见 2064 行）。
- 对齐方式：左对齐、居中和 `0` 填充（`align::numeric`，3725–3731 行）。

**【6 改动规模】**
- 预计改 1 个源文件 `include/fmt/format.h`，大概 1 到 3 处，每处几行。
- 属于局部修补：改 `size` 的计算，或让 `count_separators` 与 `apply` 保持一致。
- 不需要新增结构，也不贯穿多层。
- 测试要加在 `test/xchar-test.cc` 或 `test/format-test.cc`。

**【7 难点一句话】**
- 题面症状（只有整数部分为 0 时才错）与我读到的代码（`count_separators(significand_size)` 对所有 `exp > 0` 的值都会多算）对不上，所以真正难的是在不能运行的情况下，找出到底是哪一处让 `size` 与实际输出差 1。
- 这需要手算 `0.295`（`significand_size` 为 3，`exp` 为 0）走第三条分支时 `size` 是否正确。我读下来是 5，与实际输出一致，所以根因很可能不在第三条分支，而在第二条分支的 `count_separators`。
- 这一点请以实际复现为准。