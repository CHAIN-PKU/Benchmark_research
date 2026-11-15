## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能要一起处理的位置**
1. `src/core/lombok/javac/handlers/HandleUtilityClass.java` 的 `changeModifiersAndGenerateConstructor` 是崩溃现场：AST 上给内部类加 STATIC，又对 `innerClassDecl.sym.type` 调用 `setEnclosingType(Type.noType)`。崩溃栈在 `Types.asSuper`，很可能是符号和类型状态不一致，先弄清是哪一处改动触发。题面里「给 DTO 加 static 就能编译」说明和内部类静态化有关。
2. 同循环里方法和字段分支只改 AST 的 mods，看是否需要同步 sym 的 flags；同名重载方法在重载解析时会读取成员符号。
3. `src/core/lombok/eclipse/handlers/HandleUtilityClass.java`：并列的 Eclipse 实现，确认是否有同类问题或应保持不变。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
1. 内部类带泛型参数、字段、构造器，而不是空类 DTO。
2. `@UtilityClass` 本身是嵌套类（markStatic 与 checkLegality 的分支）。
3. 多层嵌套的内部类。
4. 重载方法与泛型方法的组合，如参数或返回类型是内部类。

**C. 仓库里已有的约定、文档、测试**
1. 看 `test/transform/resource/before/`、`after-delombok/`、`after-ecj/` 下现有 UtilityClass* 测试，沿用格式；确认测试框架是否真的触发 javac 的 Attr 阶段，delombok 输出可能看不出崩溃。
2. 同文件已有对 innerClassSymbol 的空值保护，沿用防御式风格，检查 sym 为空或类型不是 ClassType 时的行为。
3. 看 `doc/changelog.markdown` 的格式并按惯例添加修复记录。

**D. 提交前建议额外自测的情况**
1. 用题面原样代码在 JDK 11 及以上实际用 javac 编译，确认不再崩溃。
2. 显式 static 的 DTO、泛型内部类、嵌套 @UtilityClass，确认原本能编译的写法没回退。
3. 用 ecj 跑同一份代码，确认 Eclipse 路径正常、生成的静态方法和字段不变。
