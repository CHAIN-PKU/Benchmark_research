## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 其他位置
- include/fmt/format.h 的 loc_writer::operator()（约2172-2191行）：它调用带分组的十进制 write_int 重载（约2118行），该重载不看 specs.type，很可能就是 {:LX} 输出十进制的原因。
- include/fmt/format.h 的 write_int(out, arg, specs, locale_ref)（约2194-2248行）：已按 dec/hex/bin/oct/chr 分别处理，核对本地化路径怎样遵守这些类型。
- write_loc 的调用点：两个整数 write（约2262、2274行，后者用于格式串编译）和浮点 write（约3643行）；xchar.h:25 的 wchar_t 版 write_loc，以及 format-inl.h 约139行的 format_facet::do_put。
- {:Lc} 和 bool 的本地化路径也要核对。

B. 可能被检查的边界
- 各整数类型说明符加 L：x、X、b、B、o、d、c，及与 # 前缀组合。
- 负数、零、0 填充、宽度、对齐、+ 和空格符号、128位整数。
- 有分组的自定义 locale 配十六进制/二进制时是否分组，要看仓库约定和标准库行为。
- 默认 C locale 分组为空时，输出应与不加 L 完全一致。

C. 已有约定和测试
- test/format-test.cc 的 format_int_locale（约1336行）、自定义 format_facet 测试（约2245-2295行，含 [42] 与 1,234,567,89,0）改动后要保持通过。
- doc/syntax.rst、doc/api.rst 中关于 L 的描述，核对是否要同步。
- test/xchar-test.cc 里的本地化测试。

D. 提交前建议自测
1. {:LX}、{:Lx}、{:Lb}、{:Lo} 对 123456789 等值的输出。
2. 带 #、宽度、0 填充、负数的十六进制本地化格式，与不带 L 对比。
3. 自定义分组 locale 下 {:L} 十进制仍分组，并跑完 format-test 和 xchar-test 现有本地化用例。
