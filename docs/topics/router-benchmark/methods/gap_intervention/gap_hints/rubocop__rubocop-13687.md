## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) lib/rubocop/cop/lint/safe_navigation_chain.rb 的 require_parentheses? 是决定自动修正是否加括号的唯一位置,目前只处理比较运算符且父节点为逻辑/比较运算;题面场景是父节点为 pair(关键字参数/哈希值),且不限于 `-`,需考虑还有哪些父节点类型同样需要括号。2) autocorrect 里的 corrector.wrap 包裹整个 send 节点,而 `&. - 1` 是无括号带参调用,需核对包裹结果是否合法。3) add_safe_navigation_operator 对 []/[]= 有单独分支,括号处理不要与之冲突或重复。
B. 1) 其他不能省略括号的位置:关键字参数 foo(k: a&.b - 1)、哈希字面量 {k: ...}、位置参数 foo(a&.b - 1)、无括号调用 foo k: ...,逐个确认哪些需要括号。2) 其他二元运算符(+ * << ==)及一元 +@/-@;注意第44行 PLUS_MINUS_METHODS 的豁免按 node.method_name 判断,别误改。3) 已有括号或已在 &&/|| 中不应重复加括号;多层链式 a&.b.c - 1。
C. 1) spec/rubocop/cop/lint/safe_navigation_chain_spec.rb 第254-309行已有括号期望(&&、||、== 加括号,and/or 不加,单独 + 不加),需保持。2) changelog/ 下需新增条目,参考现有 fix_*.md 格式。3) cop 的 @example 文档视变化大小决定是否补充。
D. 1) 对 a&.bar(baz: a&.baz - 1) 自动修正,结果可被 Ruby 解析且二次修正幂等。2) 用 a&.baz - 1、foo(a&.baz - 1)、{k: a&.baz - 1} 确认没有多余括号或语法错误。3) 跑完整个 spec 文件,确认原有括号用例未被破坏。
