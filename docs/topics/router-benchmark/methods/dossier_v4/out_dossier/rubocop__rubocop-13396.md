**档案:`Style/RedundantParentheses` 误删含 do…end 块的括号**

**【1 题面要点】**
- 期望行为:`render json: (X.map do |k, v| ... end.to_h.camelize)` 里的括号不应被报告,也不应被自动修正。去掉括号后,`do...end` 会改绑到外层无括号的 `render` 调用上,语义随之改变,运行时出现 `String#to_h` 的 NoMethodError。
- 题面给了复现代码,也给了修正前后的文件对比。
- 题面没有给期望输出的断言,也没有给修法建议。
- 关键句:"evaluation order becomes `(render json: ExchangeRate.supported_rates.map do |k, v| ... end).to_h`"。
- 报告的消息是 "Don't use parentheses around a method call."。
- 复现用的是旧哈希语法 `:json =>`,但正文展示的是 `json:`。

**【2 相关代码】**(均在 `lib/rubocop/cop/style/redundant_parentheses.rb`)
- `:34-35`:`arg_in_call_with_block?` 的模式是 `^^(block (send _ _ equal?(%0) ...) ...)`。它只往上查两层,即 begin→send→block。
- `:74-76`:`allowed_method_call?` 调用 `arg_in_call_with_block?(node) && !parentheses?(node.parent)`。它只防住 `method (arg) { }` 这种形状。
- `:44-50`、`:52-58`:`parens_allowed?` / `allowed_expression?` 是白名单入口,新增的豁免条件最可能放在这里。
- `:40`:`on_begin` 的入口。
- `:155-165`:`check` 先调 `find_offense_message`,再对调用节点调 `check_send`。
- `:224-231`:`check_send` 和 `method_call_with_redundant_parentheses?`(`:257`)最终报 "a method call"。
- 问题发生在这里:括号内是 `send(...camelize)`,最内层是 `block(do)`。它的祖先链是 begin→pair→hash→send(render)。
- 外层没有 block 节点,所以 `arg_in_call_with_block?` 匹配不上。
- `:178` 起的 `first_arg_begins_with_hash_literal?` 是类似的祖先遍历写法,可以参考。

**【3 并列与牵连】**
- 修正走 `ParenthesesCorrector.correct`(`lib/rubocop/cop/correctors/parentheses_corrector.rb`)。修复应放在检测侧,不必动它。
- `lib/rubocop/cop/mixin/parentheses.rb` 只有 `parens_required?`,与本题无关。
- 并列场景(哈希值里的括号只是其中一种):
  - 无括号调用的普通位置参数,如 `foo (a.map do ... end).bar`。
  - `super` / `yield` 的无括号参数。
  - 括号内块出现在中间还是末尾,如 `(a.map do end.to_h)`、`(a.map do end)`、`(a do end.b)`。
  - 多层嵌套的 pair/hash/array。
- 其他 cop 不直接依赖这个逻辑(grep 没有发现别处引用)。
- 要加 changelog 条目,放在 `changelog/` 目录下,文件名格式如 `fix_...md`。

**【4 现有测试与约定】**(`spec/rubocop/cop/style/redundant_parentheses_spec.rb`)
- `:739-743`:`expect_no_offenses('method (:arg) { blah }')`,即现有的 block 豁免。
- `:413-442`:`-> do ... end` 在 `scope :my_scope, (...)` 里会报 "an expression",而 `(lambda do ... end)` 和 `(proc do ... end)` 不报。lambda/proc 括号保留已有先例。
- `:162-170`:`it_behaves_like 'redundant', '(x)', 'x', 'a method call'` 一类的共享用例。
- `:714-737`:哈希字面量作首参数的 context,写法可参考。
- `:484-504`:块体内的括号仍然会报。
- 没有外部规范。正确行为由 Ruby 语法决定:`do...end` 绑定到最外层无括号的命令调用。
- 与题面期望不冲突,但新豁免不能让 `:413` 的 `->` 用例和 `:484` 起的块体用例退化。

**【5 边界与隐含要求】**
- 隐含要求:只有"外层是无括号调用"时才豁免。`foo(json: (a.map do end))` 里的括号仍应报告。
- 块必须是 do…end:`{}` 块绑定紧,不受影响,括号仍应报告。
- 块可能不是括号内最外层节点,而是在接收者链中,如 `(a.map do end.to_h.camelize)`。要判断括号内容里是否存在 do-block。
- 括号内的 do-block 也可能嵌在更深的参数里,如 `(a(b do end))`。此时 do 绑定到 b,去括号后可能也不受影响。
- 括号与外层调用之间可能隔着 pair/hash/array 等多层节点,也可能是 `super`/`yield`。
- 自动修正的结果必须保持原样。

**【6 改动规模】**
- 1 个源文件,新增或修改 1–2 个方法,外加 1 个 spec 和 1 个 changelog。
- 属于局部修补,不需要新增结构。

**【7 难点一句话】**
难点在于把"括号内含 do…end 块"与"外层无括号调用"的条件界定得刚好:漏判会继续误删括号,多判会让现有的 `->`/块体/有括号调用的报告退化。祖先链形状多样(pair、hash、send),隐藏测试可能覆盖多种变体。