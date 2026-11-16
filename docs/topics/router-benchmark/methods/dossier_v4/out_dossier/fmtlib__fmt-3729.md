# 档案：fmt `std::filesystem::path` 增加 `n` / `g` 格式类型

下面的内容都来自对仓库的实际查证。

## 【1 题面要点】
- 要求的行为：给 `formatter<std::filesystem::path>` 的格式说明增加 *type* 字符。
  - 默认（`{}`）和 `n`：输出 `.native()`。
  - `g`：输出 generic 形式，也就是用 `/` 作分隔符。Windows 下是 `.generic_wstring()`，POSIX 下是 `.generic_string()`。
- 题面给了用法示例，没有给实现建议，也没有测试。示例如下：
  - `print("|{}|", filename);  // prints |C:\Users\zhihaoy\.cache|`
  - `print("|{:n}|", filename);  // prints .native()`
  - `print("|{:g}|", filename);  // prints .generic_wstring() |C:/Users/zhihaoy/.cache|`
  - `On POSIX, the last line prints .generic_string().`
- 题面没有说 `g` 和 `?`（debug 转义）、宽度、对齐如何组合。

## 【2 相关代码】
- `include/fmt/std.h:112-151`：`formatter<std::filesystem::path, Char>`，是主要改动点。
  - 成员有 `specs_`、`width_ref_`、`debug_`。
  - `parse`（121-134）依次解析 align、dynamic width，再解析可选的 `?`。**现在没有任何 type 字符的处理。**
  - `format`（137-150）有两条分支：非 debug 走 `get_path_string<Char>(p, p.native())`，debug 走 `write_escaped_path(quoted, p, p.native())`。
- `std.h:84-90` 的 `detail::get_path_string<Char, PathChar>(p, native)`：
  - `Char==char` 且 `PathChar==wchar_t` 时，用 `to_utf8<wchar_t>(native, replace)` 转 UTF-8。
  - 其他情况调用 `p.string<Char>()`。
  - 它只接收 native 字符串，所以实现 `g` 时要么传 generic 字符串，要么给 `p.generic_string<Char>()` 另开一条路径。
- `std.h:92-107` 的 `write_escaped_path`：同样基于 `native` 或 `p.string<Char>()`，用于 `?` 转义，三个分支结构与 `get_path_string` 平行。
- `include/fmt/format.h:2381` 的 `detail::parse_align` 和 `parse_dynamic_spec`，是 `parse` 里用到的工具。

## 【3 并列与牵连】
- 并列实现：`get_path_string` 和 `write_escaped_path` 都要能接收 generic 字符串。`format` 里两处调用（142、146）都传 `p.native()`，要改成按 `g` 选择字符串。
- 嵌套调用：
  - `std.h:211-214` 的 `formatter<std::optional<T>>` 会对底层 formatter 调 `set_debug_format(true)`，再调 `underlying_.parse(ctx)`。
  - `test/std-test.cc:40-56` 里的 ranges / optional 用例走的是同一个 path formatter，改 `parse` 时要保证它们不受影响。
  - `ranges.h` 里没有出现 path。
- 文档：`doc/api.rst:528` 只列出了 `std::filesystem::path`，没有写格式说明。`doc/syntax.rst` 里没有 path 相关内容，可补文档，但隐藏测试不会测。

## 【4 现有测试与约定】
- `test/std-test.cc:20-37` 的 `std_test.path`：
  - `:22` `EXPECT_EQ(fmt::format("{}", path("/usr/bin")), "/usr/bin");`
  - `:23` `EXPECT_EQ(fmt::format("{:?}", path("/usr/bin")), "\"/usr/bin\"");`
  - `:24` `EXPECT_EQ(fmt::format("{:8}", path("foo")), "foo     ");`
  - `:34-35` 是 `_WIN32` 下的宽字符用例，如 `"{:?}", path(L"\xd800")` 期望 `"\"\\ud800\""`。
- 隐藏测试很可能在这里加 `{:n}`、`{:g}` 的断言，以及 `{:g?}` 一类的组合，并带 `#ifdef _WIN32` 分支。在 Linux/macOS 上 `/usr/bin` 的 native 与 generic 相同。
- 约定：
  - 其他 formatter 用 `FMT_CONSTEXPR` 的 `parse`，遇到不认识的字符不会静默吞掉，而是报错。
  - 参考实现是 C++26 `std::formatter<filesystem::path>`（P2845）。我不能肯定它的 type 字符是否也是 `n`、`g`。
  - 现有代码的顺序是 align → width → `?`。题面示例是 `{:g}`，与现有语法没有冲突。

## 【5 边界与隐含要求】
- `g` 与 `?` 的组合顺序：`{:g?}` 应当可用。`?` 之前先解析 type 是否合理，需要决定。`{:?g}` 是否接受也要定。
- 非法 type 字符（如 `{:x}`）应报格式错误，现在 `parse` 返回迭代器后没有校验 `}`。
- 宽度、对齐要对 generic 结果生效。
- Windows 下 `Char==char` 要转 UTF-8；`Char==wchar_t` 与 `Char==char` 都要覆盖。在 POSIX 上只能走 `generic_string<Char>`。
- `generic_string<Char>()` 在 `Char` 为 `char`、`wchar_t`、`char8_t`、`char16_t`、`char32_t` 以外的类型时不可用。现有的 `p.string<Char>()` 也有同样限制。
- 转义路径下（`g?`），generic 字符串要经过 `write_escaped_string` 转义，不能转义两次。
- `set_debug_format` 与 optional / range 的交互要保持不变，即这些场景下不会因为多出 type 字符而改变行为。
- 在我这台 macOS 上跑不到 Windows 分支，所以 Windows 路径只能靠读代码确认。

## 【6 改动规模】
- 主要只改 `include/fmt/std.h` 一个文件，集中在 `formatter<path>` 的成员、`parse`、`format` 和两个 `detail` 辅助函数，约 4-6 处。
- 局部修补，不需要新增结构，也不贯穿多层。
- 另外可选地加 `test/std-test.cc` 用例和 `doc` 说明。

## 【7 难点一句话】
改动本身很小，难点在于 `parse` 里 `n`/`g`/`?` 的解析顺序和报错处理，以及让两个平行的 `detail` 辅助函数在 Windows 宽字符到 UTF-8 的转换下都能处理 generic 字符串。这些在本机验证不了，要靠读代码确认。