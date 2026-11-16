【1 题面要点】
- 期望行为：`where_exp` 的表达式里可以串联任意多个 `and`/`or`。题面写的是 "where_exp should work with more than 2 operators (unlimited?)"。
- 当前行为：只支持 2 个条件。第三个条件触发 `Liquid syntax error (line 4): Expected end_of_string but found id`。
- 复现：题面给了完整模板。`post.categories contains 'one' or ... 'four' or ... 'two'` 会报错，只有两个条件时正常。
- 没有给修法建议。没有期望输出，只有"不应报错"。

【2 相关代码】（`lib/jekyll/filters.rb`）
- `where_exp`，199-211 行：用 `parse_condition` 得到 condition，再对每个元素调用 `condition.evaluate(@context)`。
- `parse_condition`，419-425 行：先调用 `parse_binary_comparison`，然后 `parser.consume(:end_of_string)`。报错就来自这里，因为第三个条件还没被解析。
- `parse_binary_comparison`，434-439 行：这是根因。它只解析一个比较，读取一次 `and`/`or`，再解析一个比较后就结束：
  ```ruby
  parse_comparison(parser).tap do |condition|
    binary_operator = parser.id?("and") || parser.id?("or")
    condition.send(binary_operator, parse_comparison(parser)) if binary_operator
  end
  ```
  没有循环，所以最多两个条件。
- `parse_comparison`，447-457 行：解析单个 `左操作数 [比较符 右操作数]`，返回 `Liquid::Condition`。

【3 并列与牵连】
- `lib/` 下只有 `where_exp` 调用 `parse_condition`，没有其他调用点（grep 已确认）。
- `group_by_exp`（`lib/jekyll/filters/grouping_filters.rb:30`）使用另一套解析方式 `Liquid::Variable.new`，不涉及 `and`/`or`，不需要改。
- 文档 `docs/_docs/liquid/filters.md:127-144` 讲 `and`/`or`，只有两个条件的示例，可顺带补充，但不是必须。
- `docs/_data/jekyll_filters.yml:100-108` 里也有 `where_exp` 的示例。
- 改动只影响 `where_exp` 的表达式解析。单个条件和两个条件的表达式必须保持原有行为。

【4 现有测试与约定】
- `test/test_filters.rb:978-998` 的 "filter objects appropriately with 'or', 'and' operators" 只测两个条件：
  - `"item.color == 'red' or item.size == 'large'"`
  - `"item.color == 'red' and item.size == 'large'"`
- 其他测试：
  - 957-1061 行是 `where_exp` 的 context，涵盖 `==`、`>=`、`contains`、哈希输入、变量值比较。
  - 1017 行 `n >= 3` 是单条件用例。
- 参考实现：`parse_*` 的注释写明是改编自 `Liquid::If`（415-416 行）。依赖是 `liquid ~> 4.0`（`jekyll.gemspec:44`）。我没找到本机安装的 liquid 源码，下面这段是凭对 Liquid 4 的了解写的，没有在仓库里核对：Liquid 4 的 `If#parse_binary_comparison` 用 `while` 循环读取 `and`/`or`，每次把新 condition 用 `send(op, child)` 链到前一个上，再返回第一个 condition。
- 与题面期望没有冲突。现有测试都是两个条件，要保持通过。

【5 边界与隐含要求】
- 混合 `and`/`or`（如 `a or b and c`）的结果要和 Liquid 的 `if` 保持一致。Liquid 的链是右结合、没有优先级，隐藏测试大概率沿用这一语义。
- 要返回链头的 condition，而不是最后一个。
- 两个条件、一个条件的行为不能变。
- 三个以上同类运算符（全 `or`、全 `and`）都要能用。
- 末尾的 `consume(:end_of_string)` 保留，语法错误仍要报。

【6 改动规模】
- 只改 1 个文件、1 个方法（`parse_binary_comparison`，约 5 行）。这是局部修补，不需要新增结构。
- 另需在 `test/test_filters.rb` 增加 3 个及以上条件的测试，可选改文档。

【7 难点一句话】
改法很小：把 `tap` 换成 `while` 循环并链式连接 condition。真正需要想清楚的是链接方式和返回哪个 condition，这样混合 `and`/`or` 时求值结果才和 Liquid 原生语义一致。