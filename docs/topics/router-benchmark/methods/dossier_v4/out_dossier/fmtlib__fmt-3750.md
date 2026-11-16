【1 题面要点】
- 要求的行为：`{:LX}` 这类带 `L` 的整数格式化，也要遵守类型说明符（hex、bin、oct、`c` 等）。issue 称现在 `L` 一律输出十进制。
- 复现：`fmt::format("{:LX}", 123456789)` 输出 `123456789`，`std::format` 输出 `75BCD15`。
- 题面没有给修法建议。期望输出就是对齐 `std::format`，也就是 `75BCD15`。
- 题面没说带分组的 locale 下 hex 该怎么处理。

【2 相关代码】
- `include/fmt/format.h:2172-2191`，`loc_writer::operator()(T)`（整数重载）：
  - 它直接调用带 grouping 的 `write_int`，只支持十进制，完全不看 `specs.type`。
  - 这是根因。
- `include/fmt/format.h:2117-2135`，带 `digit_grouping` 的 `write_int`：
  - 内部写死 `count_digits` 加 `format_decimal`。
  - 前缀只处理符号（`'-'`/`'+'`/`' '`），不处理 `0x`、`0b` 这类前缀。
- `include/fmt/format.h:2193-2248`，通用 `write_int(out, write_int_arg, specs, locale_ref)`：
  - 按 `specs.type` 分支，处理 dec/hex/bin/oct/chr。
  - 最后一个 `locale_ref` 参数未使用。
- `include/fmt/format.h:2259-2276`，两个 `write(...)` 重载：
  - 先判断 `specs.localized && write_loc(...)`，成功就直接返回，不会走上面按类型分支的路径。
  - `write_loc` 的声明在 2138-2144。
- `include/fmt/format-inl.h:114-126`，`write_loc(appender, ...)`；`:139-143`，`format_facet<std::locale>::do_put`：
  - 两者最终都访问到 `loc_writer`。
- `include/fmt/xchar.h:25-37`，wchar_t 版 `write_loc`：
  - 也构造 `loc_writer<wchar_t>`。

【3 并列与牵连】
- 修 `loc_writer` 整数分支后，char 和 wchar_t 两条路径都会受益。两者共用同一个 `loc_writer`，不需要分别改。
- 带 grouping 的 `write_int` 还有第二个调用点：`format.h:4200-4202`，`group_digits_view` 的 `formatter::format`。
  - 它固定传 `digit_grouping<char>("\3", ",")`，只接受十进制。
  - 如果改了带 grouping 的 `write_int` 的签名或行为，这里要同步，不能破坏。
- `format.h:3643` 有 `specs.localized && write_loc(...)`，看起来是 bool/其他类型的 write。
  - 要确认它不受影响。
  - 本次检索中没有读它的上下文。
- 浮点路径 `format.h:2607-2733`、`2445` 也用 `digit_grouping` 或 `localized`，但属于十进制，与本题无关。
- 另一种修法：`write_loc` 对非十进制类型直接返回 false，让它走通用 `write_int`。
  - 这样改动最小。
  - 代价是十六进制不会带分组分隔符。
  - 这个取舍是否符合 `std::format` 的预期，档案里没有核实。
- chrono.h 的 `localized` 是 tm 格式化，无关。

【4 现有测试与约定】
- `test/format-test.cc:1336-1337`：`EXPECT_EQ("1234", fmt::format("{:L}", 1234));`，默认 C locale，只测十进制。
- `test/format-test.cc:2274-2276`：自定义 facet，`fmt::format(loc, "{:L}", 42) == "[42]"`，`-42` 对应 `"[-42]"`。
- `test/format-test.cc:2283-2292`：
  - 分隔符 `’` 的 1000。
  - 自定义分组 `{1,2,3}` 下，`1234567890` 得到 `"1,234,567,89,0"`。
  - 这些测试都只覆盖十进制。
- 本次检索没有找到 `test/*locale*` 文件里含 `{:L` 的断言，所以没有现成的非十进制 locale 测试。
- 外部规范是 C++20 `std::format`：`L` 作用于数值，hex 等按类型输出。在 C locale 下 `{:LX}` 应得 `75BCD15`。
- 与题面没有冲突。
- 本次检索没有读 `doc/` 对 `L` 的描述。

【5 边界与隐含要求】
- 类型：`x/X`、`b/B`、`o`、`c`、`d`、`none`。
- `#` 备用形式要带 `0x`/`0X`/`0b`/`0B`/八进制 `0` 前缀。
- `+`、空格、`-` 符号。
- 宽度、填充、`0` 填充、对齐。
- 精度对整数可能报错。
- 无效类型走 `throw_format_error`（`format.h:2245`）。
- `{:Lc}`：字符不该被分组，也不该输出成十进制数。
- 128 位整数（`uint64_or_128_t`）。
- 负数：hex 输出 `-` 加绝对值。
- 如果在 grouping 路径下支持 hex，分隔符和 `0` 填充的交互也要处理，并且要避免破坏现有 `{1,2,3}` 分组测试。
- wchar_t 路径同样要正确。

【6 改动规模】
- 主要在 `format.h` 一个文件内改动，约 1-2 处：`loc_writer` 整数分支，可能加上 `write_int` 带 grouping 的版本。
- 最小修法只需 `loc_writer` 里按类型分流，几行。
- 完整版（hex 也分组）需要把带 grouping 的 `write_int` 泛化，涉及多处。
- 属于局部修补，不需要新增大结构。
- 还要新增测试。

【7 难点一句话】
- 根因很容易定位，真正难的是判断：非十进制类型是直接绕过 locale 路径（简单），还是要让它也带分组分隔符。这一点要对齐 `std::format` 的行为，并且不能破坏现有分组和 wchar_t 的测试。