**档案：fmt 范围格式化（char 的 range / 可转 string_view 的 range）**

**【1 题面要点】**
- 要求的行为：
  - 例 1：`line | views::split(',')` 在 C++23 下应和 C++20 一样输出 `[['a'], ['b', '-', 'c'], ['d', '-', 'e'], ['f']]`。C++23 实际输出 `[a, b-c, d-e, f]`。
  - 例 2：元素类型 `X` 满足 range 且可构造 string_view，这类 range 应能编译。C++20 报 `write<char>(appender&, const X&)` 歧义。C++23 报 `std::basic_string_view<char>::basic_string_view(const X&)` 无匹配（core.h:1358）。
- 题面没有给期望输出的修法，只给了猜测：“something to do with the mapper hijacking the underlying range as a string view and then printing it unquoted. Not sure exactly.”
- 例 2 的诊断：“`core.h` checks if `string_view` is constructible from `X`, which it is, but then tries to construct it from `const X&`, which it's not”。
- 真正想要的场景：`line | views::split(',') | views::transform(views::split('-'))`，当前因 `write` 歧义而编译失败。
- 复现代码和报错都有，但没有写明例 2 的期望输出。

**【2 相关代码】**
- `include/fmt/core.h:1438-1456`：`arg_mapper::map` 的两个重载。
  - 1438 处：`is_convertible<T, basic_string_view<char_type>>` 时转成 `basic_string_view`。
  - 1447 处：`is_convertible<T, std_string_view<char_type>>` 且不可转 fmt 的 string_view 时，执行 `std_string_view<char_type>(val)`。
  - 例 2 的 C++23 错误来自这里。C++23 中 `std::string_view` 新增了 range 构造函数，是显式的 `explicit` 构造且要求右值或 borrowed。题面说 `X` 满足 `is_convertible`，但 `const X&` 构造失败。
  - 我没有核实“is_convertible 为真”的具体原因，只是读到了这个条件。
- `include/fmt/ranges.h:51-65`：`is_std_string_like`。它用 `is_convertible<T, std_string_view<char>>` 或 `find/length/data` 来检测。
- `include/fmt/ranges.h:291-296`：`write_range_entry` 中用 `is_convertible<T, std_string_view<char>>` 走字符串转义的重载。
- `include/fmt/ranges.h:298-310`：`write_range_entry` 的 char 重载和通用重载。通用重载调用 `write<Char>(out, v)`，这是例 2 在 C++20 下歧义的来源，位置对应 ranges.h:526 的旧行号。
- `include/fmt/ranges.h:376-381`：`is_range<T, Char>`，排除 string-like 和可转 std::string / std_string_view 的类型。
- `include/fmt/ranges.h:384-398`：`range_mapper::map`。有 formatter 就原样透传，否则交给 `arg_mapper` 映射。
- `include/fmt/ranges.h:400-406`：`range_formatter_type`。
- `include/fmt/ranges.h:426-518`：`range_formatter`。`format` 在 512 行调用 `underlying_.format(mapper.map(*it), ctx)`。
- `include/fmt/core.h:1866-1871`：`is_formattable` 依赖 `arg_mapper::map`。

**【3 并列与牵连】**
- core.h 里 `map` 有 `basic_string_view` 和 `std_string_view` 两个并列重载。1441-1442 和 1451-1452 两处条件都带 `!has_formatter && !has_fallback_formatter`。
- ranges.h 里 `is_std_string_like`（59-61）、`write_range_entry`（292）、`is_range`（378-380）都用 `is_convertible<T, std_string_view>`，判断口径要一致。
- tuple 的 `format_each`（ranges.h:339）也走 `write_range_entry`。
- 改 `arg_mapper::map` 会影响所有 `fmt::format` 的字符串类参数，不止 ranges。其他用到 `std_string_view` 的地方有 args.h:90、ostream.h:56、core.h:465/560、core.h:3152（`FMT_FORMAT_AS`）。
- `fallback_formatter` 相关判断分散在 core.h:1152、1442、1452、1490、1508、1533、1871 和 ranges.h:406、418、432。
- `range_formatter` 的 `maybe_set_debug_format` 控制元素是否带引号（ranges.h:451、477）。

**【4 现有测试与约定】**
- `test/ranges-test.cc:163-174`：`string_like` 同时有 begin/end 和到 string_view 的转换，断言 `EXPECT_EQ(fmt::format("{}", string_like()), "foo")`。
- `test/ranges-test.cc:397-404`：`convertible_to_string_view`，断言 `vector<convertible_to_string_view>` 格式化为 `["foo"]`。
- `test/ranges-test.cc:422-424`：`EXPECT_EQ(fmt::format("{}", std::vector<char>{'a', 'b'}), "['a', 'b']")`。
- `test/ranges-test.cc:392`、388 等：字符串元素带转义引号。
- 我没有在测试里找到 `std::ranges`、`views::split` 或 `transform` 的用例，需要新增。
- 约定：range 的元素是 char 时输出 `'a'`，string 元素输出 `"..."`。C++20 的输出是参照。
- 与题面不冲突：已有的 `string_like` 要求 “既是 range 又可转 string_view 时当字符串输出”。这与例 1 的期望有张力。`split_view` 的子 range 是 range，C++23 下可构造 string_view，要让它按 range 而不是字符串输出，同时 `string_like` 仍按字符串输出。这个区分条件怎么定，仓库里没有现成的说法。
- 外部规范：C++23 `std::formatter` 对 range 的约定，我没有在仓库里验证，不确定。

**【5 边界与隐含要求】**
- 区分“隐式可转换到 string_view”（应走字符串）与“只能显式构造”（C++23 range 构造，应走 range）。
- 例 2 在 C++20 的歧义要解掉，需要 `X` 作为 range 元素时走 range 格式化，输出嵌套，而不是自己的 `write`。
- 嵌套 `transform(split('-'))` 要得到 `[[['a']], [['b'], ['c']], ...]` 的形式，每层元素类型是 char 的 range。
- 非 const 的 begin/end（例 2 中 `X` 只有非 const `begin()`）需要走 `maybe_const_range` 路径。
- `std::views::split` 的元素是 `subrange`，它是 view 且 `begin/end` 是 const。
- 要同时在 C++20 和 C++23 下编译通过，测试大概率用 `#ifdef` 保护。
- wchar_t 重载是否同样处理，题面没提。

**【6 改动规模】**
- 估计 1-2 个文件（core.h、ranges.h），各 1-3 处，加测试文件 ranges-test.cc。
- 局部修补为主：收紧 `map` 的 SFINAE 条件，调整 `write_range_entry` 或 `is_std_string_like` 的条件。
- 不太需要新增结构，但这是模板元编程，条件要在 C++11/14/17/20/23 多个标准下通过。

**【7 难点一句话】**
难在判定“range 又可转 string_view”的类型何时按字符串、何时按 range 输出，又要同时兼顾 C++20 的 `write` 歧义和 C++23 的 string_view 构造这两条不同的失败路径，还不能让现有 `string_like` 测试回归。