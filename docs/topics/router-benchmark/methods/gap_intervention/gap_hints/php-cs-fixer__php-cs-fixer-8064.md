## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) SimpleToComplexStringVariableFixer::applyFix 只匹配 `${` + T_STRING_VARNAME + CT::T_DOLLAR_CLOSE_CURLY_BRACES 三个 token 的形态；`${name['key']}`/`${name[0]}` 的 token 序列不同，先打印 token 再决定怎么匹配。2) 同一方法里循环起点 count-3、$index+2 和 overrideRange 的范围是按固定三个 token 写的，内容变长后要核对。3) 输出所需的关闭 token 类型要和仓库里其他生成 `{$var[...]}` 的代码一致，参考 ExplicitStringVariableFixer。
B. 1) 索引为变量或字符串：`${name[$i]}`、`${name["k"]}`、`${name[-1]}`。2) heredoc 中的写法。3) 一个字符串里多个 `${}`，以及简单形式与数组形式混用。4) `${name}` 前紧挨 `$` 的转义处理要保持。5) 非简单变量形式 `${expr()}`、`${name->prop}`、`${$a}` 和嵌套方括号不应被误改或报错。
C. 1) 测试文件 tests/Fixer/StringNotation/SimpleToComplexStringVariableFixerTest.php 的数据集风格和「不应修改」用例。2) getDefinition 的 CodeSample 与 doc/rules 文档是否需同步。3) getPriority 注释要求在 ExplicitStringVariableFixer 之后运行，核对联用结果。4) 最低支持 PHP 版本，以及不同版本下 tokenizer 输出的差异和测试里按版本区分的写法。
D. 1) 题面两个例子加 `[$i]`、`["k"]`。2) heredoc 内的 `${name[0]}`，以及同一字符串多个 `${}` 混用。3) 不应改动的输入输出须与输入一致，并重复运行确认幂等。
