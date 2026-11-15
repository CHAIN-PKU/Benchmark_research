## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 可能要一并处理的位置
1. include/fmt/std.h 的 detail::get_path_string 与 detail::write_escaped_path：两者只接收 p.native()，且有 char/wchar_t、Char==PathChar、其他三种分支；generic 格式要覆盖三个分支，也要覆盖调试(?)路径。
2. formatter<std::filesystem::path>::parse：现有顺序是对齐、宽度、?；n/g 类型字符放哪里要对照其他 formatter；解析后要检查多余字符，非法字符要报错。
3. ranges/optional 会调用 set_debug_format，path 在 range 内的行为不能被破坏。

B. 可能被检查的边界输入
1. 组合格式串：{:g?}、{:?g}、{:>10g}、{:10n}、{:{}g}（动态宽度）；哪些合法，调试转义用原生还是 generic 路径。
2. 字符类型：wchar_t 格式串、Windows 上 char 配 wchar_t 转换；含非法 UTF-16（如 \xd800）的路径在 generic 下也应与现有替换字符行为一致。
3. 无分隔符路径、空路径、含引号路径；POSIX 上 g 与 n 输出应相同。

C. 仓库已有约定
1. test/std-test.cc 的 TEST(std_test, path) 已有 {}、{:?}、宽度、\xd800 用例，沿用写法并保证原输出不变。
2. doc/api.rst 第 528 行附近与 ChangeLog.md 关于 path 的说明，需核对是否同步。
3. 其他 formatter 对类型字符的处理（std.h 其他 parse、core 中对非法 spec 抛 format_error 的做法）。

D. 提交前建议自测
1. POSIX 上 path("a/b") 分别测 {}、{:n}、{:g}，输出应一致。
2. 测 {:g?} 与 {:?g}，确认合法性与转义结果。
3. 测 {:>12g}、{:{}g} 带宽度，非法类型如 {:x} 应报错，并测 fmt::format(L"{:g}", path)。
