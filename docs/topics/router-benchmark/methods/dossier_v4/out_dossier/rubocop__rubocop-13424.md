**档案：Style/SafeNavigation 自动修正产生过长安全导航链**

**【1 题面要点】**
- 期望行为：自动修正不应引入新的违规。题面给了三种可接受的结果：“Either autocorrecting now expands safe navigation chains, ignores/encourages object checks, or the offence isn't autocorrectable”。
- 复现：`foo && foo.bar.abc&.xyz&.name`。`Style/SafeNavigation` 报告违规，`--autocorrect-all` 把它改成 `foo&.bar&.abc&.xyz&.name`。这个结果又触发了 1.68 新增的 `Style/SafeNavigationChainLength`（默认 Max 2）。
- 题面没有给出具体修法。它只给出三选一的方向，没有期望输出，也没有指定具体实现。
- 代码里的实际原因我已查到（见第 2 节）：`chain_length` 数链长时漏掉了已有的 `&.`（csend）。

**【2 相关代码】**
- `lib/rubocop/cop/style/safe_navigation.rb:314-320`，`chain_length(method_chain, method)`：
  - 它用 `method.each_ancestor(:send)` 数链长。
  - 在 rubocop-ast 里，`&.` 调用的节点类型是 `:csend`，不是 `:send`。所以 `each_ancestor(:send)` 遇到已有的 `&.` 就不计数。
  - 对 `foo.bar.abc&.xyz&.name`，只会数到 `bar`、`abc` 共 2 个，不超过 `MaxChainLength` 默认值 2，所以仍判为违规。
- `safe_navigation.rb:229-237`，`offending_node?`：
  - 第 232 行调用 `chain_length(rhs, rhs_receiver) > max_chain_length`。
  - `on_if` 和 `on_and` 都经由它判定。
- `safe_navigation.rb:374-376`，`max_chain_length`：读取 `cop_config['MaxChainLength']`，默认 2。
- `safe_navigation.rb:360-372`，`add_safe_nav_to_all_methods_in_chain`：给链上所有非 `&.` 的 send 补 `&`。
- `lib/rubocop/cop/style/safe_navigation_chain_length.rb:29-43`：
  - 新 cop。从每个 `on_csend` 往上数连续的 csend 祖先，数量 `>= max`（默认 `cop_config['Max'] || 2`）就报告。
  - 注意这里的报告阈值是 `size >= max`，和 `MaxChainLength` 的 `>` 比较不对称，对齐时要小心。
- `config/default.yml:5279-5284`：该 cop 为 `Enabled: pending`，`Max: 2`。

**【3 并列与牵连】**
- `on_if`（141-155）和 `on_and`（157-179）都走 `offending_node?` → `chain_length`。修改 `chain_length` 或 `offending_node?` 会同时影响 `if`/`unless`/修饰符形式和 `&&` 形式。
- `unsafe_method_used?`（322-332）同样用 `each_ancestor(:send)`，和 `chain_length` 一样会漏掉 csend。这里要不要一并处理，需要判断。
- `SafeNavigationChainLength` 的文档（第 11-19 行）已经承认两个 cop 可能互相冲突，并举了 `Max: 1` 的例子。
- 两个配置项相互独立：`Style/SafeNavigation: MaxChainLength` 和 `Style/SafeNavigationChainLength: Max`。
- 另一个相关点：`Lint/SafeNavigationChain` 在 `unsafe_method_used?` 里被查询。

**【4 现有测试与约定】**
- `spec/rubocop/cop/style/safe_navigation_spec.rb:39-40`：`expect_no_offenses('user && user.one.two.three')`，超过 2 个方法的链不报。
- 同文件 `:43`、`:47` 有长链加 block、长链加 nil 检查的不报用例。
- `:316-323`：`#{variable}&.one&.two(baz) { |e| e.qux }`。已有 `&.` 的链被修正成多个 `&.`，用例里是 `foo && foo.one.two(baz) {…}`（两个方法，没超限）。
- `:507-521`：`MaxChainLength: 1` 的 context。
- 我没有在现有 spec 里看到“链里已有 `&.`”的专门用例。
- 约定：新增 fix 要在 `changelog/` 下加 `fix_*.md`。
- 外部规范：无硬性规范。三选一的取舍由维护者决定，题面没有断言。

**【5 边界与隐含要求】**
- 选择“不报违规”还是“报但不修正”：
  - 如果只是让 `chain_length` 计入 csend，违规就消失，`foo && foo.bar.abc&.xyz&.name` 会变成无违规。
  - 题面的措辞更偏向“不要再引入新错误”，两种做法都说得通。
- 链里 csend 的位置：可能在 receiver 之前（如 `foo.bar&.baz`），也可能在之后。receiver 之前已有的 `&.` 对修正后的链长没有影响，所以不能不加区分地一并计数。
- block 的影响：`add_safe_nav_to_all_methods_in_chain` 遇到 block 节点会继续往上，而 `chain_length` 的 `each_ancestor(:send)` 会跳过 block。两边对 block 的处理不一致。
- 是否要考虑 `SafeNavigationChainLength` 被禁用或未启用（pending）时的行为。
- `on_and` 的多子句 `&&` 链里，每个子句都会走一遍。
- 隐藏测试大概率包含 `foo && foo.bar.abc&.xyz&.name` 这类输入。

**【6 改动规模】**
- 1 个源文件，大概 1–3 处（主要是 `chain_length`，可能连带 `unsafe_method_used?`），再加 1 个 changelog 文件和若干 spec。
- 局部修补，不需要新增结构。

**【7 难点一句话】**
改动本身很小，难在要先看出根因是 `each_ancestor(:send)` 漏掉 `:csend`，再在“把已有 `&.` 计入链长”“按两个 cop 的阈值联动”“只关掉自动修正”这几种做法里，选出和隐藏测试断言一致的那一种。