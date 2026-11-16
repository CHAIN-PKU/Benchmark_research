正在收尾：核对完 `on_zero` 及相关调用点，下面直接输出档案。

# 仓库档案：fmt `{:<06}` / `{:>06}` 对齐与 `0` 同时出现

## 【1 题面要点】
- 要求：对齐选项与 `0` 同时出现时忽略 `0`。题面引用 cppreference：“If the 0 character and an align option both appear, the 0 character is ignored.”
- 复现与期望都有：
  - `fmt::print("{:<06}\n", -42); // expected: "-42   ", actual: "-42000"`
  - `fmt::print("{:>06}\n", -42); // expected: "   -42", actual: "000-42"`
- 没有给修法建议。

## 【2 相关代码】
- `include/fmt/core.h:2239-2242` `specs_setter::on_zero()`：
  ```cpp
  if (specs_.align == align::none) specs_.align = align::numeric;
  specs_.fill[0] = Char('0');
  ```
  - 这是最可能的根因。已有显式对齐时，`align` 保持不变，但 `fill[0]` 仍被无条件改成 `'0'`。
  - 后续按 `<` 或 `>` 填充时，填充字符就是 `'0'`，这正是 `-42000` 和 `000-42` 的来源。
- `core.h:2662-2665` `parse_format_specs`：先解析对齐，再解析符号和 `#`，最后遇到 `0` 就调用 `handler.on_zero()`。所以 `on_zero` 被调用时，`specs_.align` 已经是 `left` 或 `right`。
- `core.h:2958-2961` `specs_checker::on_zero()`：只做“需要数值参数”的检查，然后转发给 `Handler::on_zero()`。
- `include/fmt/format.h:1898-1916` `write_int_data`：`align::numeric` 时才计算 0 填充。
- `format.h:1923-1944` `write_int`：用 `write_padded<align::right>` 写入，填充字符取自 `specs.fill`。
- `format.h:3319-3325` 浮点路径：`align::numeric && sign` 时先输出符号，并让 `width--`。
- `format.h:2282-2285` `write_nonfinite`：`fill == '0'` 时换成空格。

## 【3 并列与牵连】
- `specs_setter` 有两个子类，都继承 `on_zero`，改基类即可同时覆盖：
  - `dynamic_specs_handler`（`core.h:2255`）
  - `specs_handler`（`format.h:3598`）
- `printf.h` 是独立的解析路径（`:313-314`、`:343`、`:428-447`），按 printf 规则处理 `0` 标志，与本题无关。
  - 它自己的规则是“有 `-` 时忽略 `0`”。
  - 不应被连带改动。
- 其他调用 `parse_format_specs` 的地方（如 chrono、ranges 的 formatter）也经过 `specs_setter`。修改会自动影响它们，需确认没有测试依赖旧行为。
- `write_nonfinite` 里那段把 `'0'` 填充换成空格的代码，是旧机制的补丁。修复后只有 `{:06}` 这类 `align::numeric` 情形才会让它生效。

## 【4 现有测试与约定】
- `test/format-test.cc:836`：`EXPECT_EQ(fmt::format("{:>06.0f}", 0.00884311), "000000");`
  - **与题面期望直接冲突**。按新规则 `>` 加 `0` 应忽略 `0`，结果应是空格填充：`"     0"`。
  - 这条断言必然要改。隐藏测试大概率已更新它，并可能新增 `{:<06}` / `{:>06}` 的断言。
- `format-test.cc:783-790`：`{0:05}` 的结果是 `-0042`、`00042`、`-000042`，是不带对齐的 `0` 路径，应保持不变。
- `format-test.cc:1452-1455`、`1474-1478`：NaN / inf 在 `{:+06}`、`{:<+06}`、`{:^+06}`、`{:>+06}` 下都是空格填充。
  - 修复后这些断言结果不变。
  - 其中 `<`、`^`、`>` 本来就走“0 被换成空格”的路径。
- `test/core-test.cc:623`：`static_assert(parse_dynamic_specs("0").align == fmt::align::numeric, "")`。
  - 只有 `0`、没有显式对齐时仍要得到 `align::numeric`。
  - 这是约束：不能把 `align::numeric` 的设置去掉。
- `core-test.cc:553`：测试用 handler 自带 `on_zero() { res = zero; }`，说明 `on_zero` 是 handler 接口的一部分，签名不宜改。
- 外部规范：cppreference 和 C++20 `std::format` 规定，对齐存在时 `0` 被忽略。仓库内没有其他文档与之矛盾。

## 【5 边界与隐含要求】
- 显式填充加对齐：`{:*<06}` 应保留 `*` 作填充，`0` 被忽略。若只判断 `align != none` 就不动 `fill`，这点自然成立。
- 只有 `0`、没有对齐：`{:06}` 要保持 `align::numeric` 且 `fill = '0'`。
- 浮点同理：`{:<06.1f}`、`{:^08.2f}` 的符号和填充要正确。
- 十六进制、二进制等带前缀的整数：`{:<#06x}` 不应再出现前缀后插 0。
- `0` 出现在对齐之前的写法：`{:06<}` 不是合法语法，不必处理。
- 非数值参数：`specs_checker::on_zero` 仍应报错，如 `{:<05}` 配字符串。
- 若 `fill` 被显式设为 `'0'`（如 `{:0<6}`），这是“填充字符为 0”，应保持有效，不能被误判为 `0` 标志。
- 文档里若描述了 `0` 的行为，可能需同步。本次只检索了代码与测试，`doc/` 未深查。

## 【6 改动规模】
- 核心改动：`core.h` 一个函数、1-2 行。比如只在 `align == none` 时才设置 `numeric` 和 `fill`，其余情况不做任何事。
- 测试：`format-test.cc:836` 需要改期望值，并新增几条断言。
- 属于局部修补，不新增结构，也不贯穿多层。

## 【7 难点一句话】
定位和修改都很简单（`specs_setter::on_zero` 里无条件的 `fill[0]='0'`），难点在于发现 `format-test.cc:836` 这条现有断言与新规则冲突，并确认 NaN/inf、显式填充字符和 `core-test` 的 `align::numeric` 约束不被改坏。