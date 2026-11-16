**档案：`String.format` / `.formatted` 在文本块（text block）上无法解析**

**【1 题面要点】**
- 要求的行为：对文本块字面量调用方法，例如 `"""\n Hello %s!\n """.formatted("world")`，`JavaParserFacade.solve(MethodCallExpr)` 应解析成功，得到 `java.lang.String.formatted(java.lang.Object...)`，行为与普通字符串字面量一致。
- 复现：题面给了完整的两个文件，用 `ReflectionTypeSolver(false)`，Java 21，版本 3.26.2。
- 期望输出（照抄）：`Could solve: """ ... """.formatted("world") as java.lang.String.formatted(java.lang.Object...)`
- 题面给出的异常（照抄）：`UnsolvedSymbolException{... cause='java.lang.UnsupportedOperationException: com.github.javaparser.ast.expr.TextBlockLiteralExpr'}`
- 题面没有给修法建议。但这个异常信息已经直接指向根因。

**【2 相关代码】**
- `javaparser-symbol-solver-core/.../javaparsermodel/TypeExtractor.java:286`：`visit(StringLiteralExpr, Boolean)` 返回 `stringReferenceType`。这个字段在第 66 行声明，第 76 行初始化为 `LazyType(... typeSolver.solveType(JAVA_LANG_STRING))`。
- `TypeExtractor.java` 里没有任何 `TextBlockLiteralExpr` 的重写。我对整个 symbol-solver-core/src/main 做了 grep，唯一匹配是下一条。
- `.../javaparsermodel/DefaultVisitorAdapter.java:528`：`visit(TextBlockLiteralExpr, Boolean)` 直接 `throw new UnsupportedOperationException(node.getClass().getCanonicalName())`。`TypeExtractor` 继承自它，因此文本块走到这里就抛异常，与题面异常吻合。
- 在 AST 里，`TextBlockLiteralExpr`（`javaparser-core/.../ast/expr/TextBlockLiteralExpr.java:47`）和 `StringLiteralExpr`（第 48 行）是并列的，都继承 `LiteralStringValueExpr`。

**【3 并列与牵连】**
- 同类的字面量（Integer、Long、Char、Double、Boolean）在 `TypeExtractor` 里都有重写。`TextBlockLiteralExpr` 是字面量里唯一漏掉的。
- 同样的遗漏有没有，我没有逐个确认。`DefaultVisitorAdapter` 里很多节点都是 throw，但那些不是字面量，不在本题范围内。
- 改 `TypeExtractor` 只影响类型推断（`calculateType`、方法参数类型和作用域类型）。`JavaParserFacade` 和 `JavaSymbolSolver` 都通过它调用，所以文本块作为方法实参、变量初始化、拼接表达式等场景也会一并受益。
- 我没有找到类似 `if (expr instanceof StringLiteralExpr)` 之类的特判分支，symbol-solver-core 里 `StringLiteralExpr` 只出现在 TypeExtractor 和注解成员声明的转换里。

**【4 现有测试与约定】**
- symbol-solver-testing 里没有文本块的解析测试。唯一匹配的 `Issue546Test.java` 只是用了 `normalizeEolInTextBlock` 这个工具函数（第 24、59 行），与本题无关。
- 没有参考实现。约定上，字面量的类型由 `TypeExtractor` 的 `visit` 返回。
- 外部规范（JLS）：文本块的类型是 `java.lang.String`。与题面期望一致，不冲突。
- 解析测试通常放在 `javaparser-symbol-solver-testing/src/test/java/.../Issue*Test.java`，隐藏测试大概率是类似的新增 Issue 测试。我没有读它的具体写法。

**【5 边界与隐含要求】**
- 需要用 Java 15 及以上的语言级别解析，否则文本块本身解析不了。测试配置要设置语言级别，测试自己应该会处理。
- 类型必须与 `StringLiteralExpr` 一致，即复用 `stringReferenceType`（懒加载，避免提前要求类型求解器能解析 `java.lang.String`）。
- 文本块内容里带 `\n`、转义、缩进都不影响类型，不需要处理内容。
- 同时可能还要考虑 `DefaultVisitorAdapter` 里的 throw 是否保留。`TypeExtractor` 重写后它不会再被调用到。

**【6 改动规模】**
- 1 个文件、1 处：在 `TypeExtractor.java` 里新增 `visit(TextBlockLiteralExpr, Boolean)` 返回 `stringReferenceType`，另加 import。
- 局部补丁，不新增结构，不贯穿多层。再加一个测试，用例本身也很小。

**【7 难点一句话】**
这道题很简单：根因明确（`TypeExtractor` 漏了 `TextBlockLiteralExpr` 的重写，落到父类抛异常），修法是照着 `StringLiteralExpr` 补一个方法，主要风险只在测试用到的语言级别设置和 import 上。