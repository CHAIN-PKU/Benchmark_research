## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 可能需要一并处理的位置
1. `lib/rubocop/cop/style/sole_nested_conditional.rb` 的 `insert_bang`：`unless` 转 `if` 时加 `!` 的逻辑，题面里的 `if_branch.unless?`（内层 modifier unless）走的是 `autocorrect_outer_condition_basic` 里的 `and_operator = ' && !'`，并不经过 `insert_bang`。要分清这两条路径，别只改一条。
2. 外层是 `unless` 的路径（`correct_from_unless_to_if` → `insert_bang`）和外层是修饰符形式的路径（`autocorrect_outer_condition_modify_form`、`replace_condition`），都会给条件加否定。它们对复合条件的包裹规则各不相同，需要核对。
3. `wrap_condition?`、`wrap_condition`、`replace_condition`、`require_parentheses?` 是并列的"是否要加括号"判断，注意它们现在的判断范围（运算符关键字、无括号带参调用）是否覆盖了题面里 `!` 之后跟比较方法（`===`）的情况。比较方法在 `correct_outer_condition` 里被明确排除过。
4. 内层条件是 `unless` 且为修饰符形式的 `correct_for_guard_condition_style`，是题面场景的实际入口。

B. 可能被检查的输入/边界
1. 内层 `unless` 的条件是各种二元运算符调用：`==`、`===`、`=~`、`<`、`+`、`<=>`，以及无括号、带参数的普通方法调用（如 `foo.bar arg`）。要弄清哪些需要括号，哪些不需要。
2. 内层条件是 `and`/`or`/`not` 关键字、带 `!` 的条件、已带括号的条件、`defined?`、三元表达式、块调用。
3. 内层是块形式的 `unless`（非修饰符）和修饰符形式，两种写法都要覆盖。
4. 外层 `unless` 加内层 `unless`，以及外层是修饰符形式（`... end if a`）时的组合。

C. 仓库约定、文档和测试
1. `spec/rubocop/cop/style/sole_nested_conditional_spec.rb` 已有大量围绕括号、`unless`、比较方法、`||`、赋值的用例。新增用例要照它们的风格写，并核对现有用例的期望输出不被破坏。
2. `autocorrect_incompatible_with` 声明了与 `Style::NegatedIf`、`Style::NegatedUnless` 互不兼容，改动不要破坏这一点。
3. 仓库根目录的 `changelog/` 目录有按条目一个文件的约定，修 bug 通常需要在那里新增一条，可参考现有文件的命名和格式。
4. `Style/NegatedIf` 一类的 cop 里也有对 `!` 加括号的相似处理，可对照。

D. 提交前建议额外自测
1. 题面原例 `result = false unless t === value.public_send(a)`，嵌套在 `if result` 里，检查生成的代码语法合法，并且 `!` 作用于整个比较。
2. 内层 `unless` 的条件是无括号带参数的方法调用，以及 `a == b`、`a && b` 这类条件，查看输出语义是否等价。
3. 外层 `unless` 加内层修饰符 `unless`，或外层是修饰符形式，检查所有现有 spec 仍通过，并确认自动修正结果是否稳定（二次运行无新违规）。
