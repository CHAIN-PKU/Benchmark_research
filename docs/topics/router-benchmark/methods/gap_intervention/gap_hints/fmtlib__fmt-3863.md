## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名、但很可能也要一起处理的位置
1. include/fmt/ranges.h：range_format 枚举已有 string 和 debug_string，但 range_format_kind_（约第 454 行）从不返回它们；range_default_formatter 的特化只覆盖 sequence/map/set。要让 s 和 ?s 生效，这几处很可能都要改。
2. range_formatter::parse（约第 410 行）只认 n 和 ':'，其他字符一律报 invalid format specifier，这是题面报错的来源。s、?s 要在这里解析，并与 n 的处理协调。
3. range_formatter::format 目前逐元素输出并加括号和分隔符，字符串模式需要另一条路径。可参考 include/fmt/std.h 里 set_debug_format 的用法，以及 format.h 的 write_escaped_string。
4. 宽字符的 Char 模板参数也走同一套代码，要一并考虑。

B. 题面没给例子、但很可能被检查的输入/边界
- 元素类型不是 char 的 range（如 vector<int>）用 {:s}，应继续报错，不能误当字符串。
- 空 range 的 {:s} 和 {:?s}。
- 含转义字符、引号、非法 UTF-8 的内容在 ?s 下的输出。
- s 与 n 组合：n 去括号在字符串模式下含义不明。
- 嵌套：vector<vector<char>>、tuple<vector<char>>。

C. 仓库里已有的约定、文档或测试
- test/ranges-test.cc 第 517–538 行已有断言：{} 对 vector<char> 输出 ['a', 'b']，对 vector<vector<char>>{{'x'}} 输出 [['x']]，对 tuple<vector<char>> 输出 (['x'])，默认行为不能变。
- test/ranges-test.cc 第 60–67 行有 {:n:n:}、{::} 等冒号嵌套写法的断言，不要破坏。
- doc/syntax.rst 的 Range Format Specifications 一节只写了 [":" [underlying_spec]]，新增说明时要同步更新文档。
- 第 450 行的 range_format 枚举已预留 string 和 debug_string，应沿用这些名字。

D. 提交前建议额外自测
1. fmt::format("{:s}", vector<char>{'H','\t','l','l','o'}) 与 "{:?s}" 的输出要和题面表格一致。
2. {:s} 作用于 vector<int>，以及 {:?}（没有 s），看是否仍报错或符合预期。
3. 回归：{}、{::}、{:n}、{::d} 对 vector<char> 的输出要和现有测试一致。
