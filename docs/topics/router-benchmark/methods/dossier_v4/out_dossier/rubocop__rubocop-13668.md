**【1 题面要点】**
- 期望行为：把内层条件合并进外层时，要保持原有的运算优先级，必要时加括号。
- 题面给了复现、期望输出和实际输出，没有给修法建议。
- 复现代码：`if result` 里嵌套 `result = false unless t === value.public_send(a)`。
- 期望：`if result && !(t === value.public_send(a))`。
- 实际：`if result && !t === (value.public_send(a))`。
- 实际输出的语义已经变了：`!t` 先求值，再做 `===`。
- 触发点是内层为 `unless`，且条件是不带括号的比较方法调用，同时带参数。

**【2 相关代码】**
文件是 `lib/rubocop/cop/style/sole_nested_conditional.rb`。
- `autocorrect`（98）：外层条件是 or 或赋值时包括号，然后分派到两种形态。
- `autocorrect_outer_condition_basic`（110）：外层是普通形态。内层 `unless` 时用 `' && !'` 作为连接符，之后调用 `correct_for_guard_condition_style`（136，内层是修饰形态）或 `correct_for_basic_condition_style`（145）。
- `wrap_condition`（155）：对 `operator_keyword?` 或带参数且无括号的 call 做包裹。
  - 对 call 走 `parenthesized_method_arguments`（253），产生 `t ===(value...)` 这种形式；这里的 `===` 是比较方法。
  - 这正是 bug 的来源：它只给参数加括号，没有给整个表达式加括号，前面的 `!` 就绑到了 `t` 上。
- `replace_condition`（243）：和 `wrap_condition` 并列，供修饰形态使用，逻辑相同。
- `wrap_condition?`（239）：判断是否需要包裹，没有排除比较方法。
- `insert_bang`（203）：处理外层 `unless` 转 `if`。已经对比较方法单独用 `!(…)` 包裹。
- `correct_for_outer_condition_modify_form_style`（171）：外层是修饰形态。

**【3 并列与牵连】**
- 有至少 3 处调用点需要同样处理：
  - `wrap_condition`（152 行调用，非修饰形态）。
  - `replace_condition`（138 行用于内层修饰形态，174 行用于外层修饰形态）。
  - `correct_outer_condition`（190）和 `require_parentheses?`（228）已经排除比较方法。
- 这里有一个不对称：只有「内层 unless 加 `!`」的路径会受影响。内层 `if` 时，`a && t === x` 不需要括号。
- 外层 `unless`（`insert_bang`）已经处理比较方法。
- 内层 `unless` 的各条路径还需检查：
  - 基本形态：`if a \n unless b`。
  - 内层修饰形态：`if a \n b unless c`。
  - 外层修饰形态，内层 `unless`：`correct_from_unless_to_if` 带 `is_modify_form`，走 `insert_bang`（206 行）的 `wrap_condition?` 分支。
- 修改 `wrap_condition?` 会同时影响所有这些调用点，需要避免改变现有用例的输出。

**【4 现有测试与约定】**
文件是 `spec/rubocop/cop/style/sole_nested_conditional_spec.rb`。
- 57-70 行：`unless foo == bar` 变成 `if !(foo == bar) && baz`。外层路径已经有这个约定。
- 注释写着 `Style/InverseMethods` 会在之后继续修正。
- 149-165 行：`unless h.has_key?(:b)` 变成 `&& !h.has_key?(:b)`。
- 172-181 行：`unless bar && baz` 变成 `!(bar && baz)`。
- 299-341 行：非比较方法带参数 `foo.is_a? Foo` 变成 `!foo.is_a?(Foo)`。
- 369、379 行：`if` 带无括号参数时，参数被括起来。
- 现有测试里没有「内层 `unless` 加比较方法」的用例。
- 没有与题面冲突。题面期望的 `!(t === …)` 与 57-70 行的既有风格一致。

**【5 边界与隐含要求】**
- 内层 `unless` 的条件是哪些比较方法：`==`、`===`、`<`、`>`、`=~`、`!=` 等。
  - 带括号的 `t === (x)` 和不带括号的两种写法都要正确处理。
  - 带括号的情况 `!t === (x)` 仍然错误，因为 `!` 优先级高于 `===`，所以也应该被 `!(…)` 包住。
- 一元 `!` 加二元运算符，对应 `!(a == b)`。
- 内层条件带 block 的情况（`wrap_condition` 里 `block_type?` 取 `send_node`）。
- 内层修饰形态与基本形态都要覆盖。
- 外层修饰形态 + 内层 `unless`（`insert_bang` 的 `is_modify_form` 路径）。
- 内层条件是 `!` 本身、`and`/`or` 关键字、三元表达式、`defined?`、`not` 等，是否也有优先级问题。
- 修改后不能破坏 Style/InverseMethods、NegatedIf 等其他 cop 的互操作。

**【6 改动规模】**
- 改动 1 个 cop 文件，约 1-3 处，属于局部修补。
- 另外要加一个 changelog 条目和若干 spec。
- 不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
难点是找准路径：内层 `unless` 的 `!` 前缀与无括号带参数的比较方法组合，走的是 `wrap_condition`/`replace_condition` 的参数括号化分支。要加的是整体 `!(…)` 括号，而不是参数括号，同时还要保证其他已有输出不变。