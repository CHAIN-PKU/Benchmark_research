## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 并列位置/调用点**
1. `include/fmt/format.h` 的 `formatter<group_digits_view<T>>::format`(约 4126 行):调用 `write_int` 时把值强转为无符号、prefix 固定为 0,负数变补码大数且丢符号。同文件 `loc_writer::operator()`(约 2156 行)是已有参照,它用 `make_write_int_arg(value, specs.sign)` 拆出绝对值和 prefix。注意 `parse` 用 `type::int_type`,`{:+}`、`{: }` 也应被考虑(`specs.sign`)。
2. `make_write_int_arg`(约 2134 行)用 `uint32_or_64_or_128_t<T>`,而 `format` 里用 `uint64_or_128_t<T>`,两者对窄类型位宽不一致,要核对转换与取反顺序是否得到正确绝对值。
3. `group_digits_view<T>` 对 T 无约束;最小值(INT_MIN/INT64_MIN)取反要走无符号运算。

**B. 边界输入**
1. 多种有符号类型:int、long long、short、signed char,以及 128 位整数(如平台支持)。
2. 最小值 INT_MIN、LLONG_MIN。
3. 分组边界负数:-999、-1000、-123456。
4. 宽度/填充/对齐:{:10}、{:<10}、{:010}、{:^10},核对符号与零填充、分组逗号的交互及宽度是否计入符号。
5. 符号标志:{:+}(正/负)、{: }。

**C. 已有约定/文档/测试**
1. `test/format-test.cc` 的 `TEST(format_test, group_digits_view)`(约 1837 行)目前只有正数用例,可按其风格补负数。
2. 对照普通整数的 `{:,}`/`L` 本地化路径(`write_int`、`digit_grouping`)在负数+零填充+宽度时的输出,`group_digits` 应与之一致;可在 test/format-test.cc、locale 相关测试里找对照。
3. `doc/api.rst` 与 `format.h` 中 `group_digits` 注释只有正数例子,行为变化时留意是否同步。
4. 检查 include/fmt 下是否有别处重复该 view/formatter(如 xchar.h)。

**D. 提交前自测**
1. `group_digits(-12345)` 得到 `-12,345`;再测 INT_MIN/LLONG_MIN 与 0。
2. `{:+}` 配正数与负数,与 `fmt::format("{:+}", -12345)` 的符号表现对比。
3. `{:12}`、`{:012}` 配负数,与无分组的 `{:012}` 对比符号位置与宽度;另测 unsigned 类型确认未被改坏。
