## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名、但很可能要一起处理的位置
1. `src/core/lombok/bytecode/AsmUtil.java` 的 `fixJSRInlining` 用 `new FixedClassWriter(reader, 0)`，同样把原类的常量池带进了新类。两个 Remover 都会先调用它，所以只改 Remover 里的 writer 还不够。这一步生成的字节码里，`Lombok.sneakyThrow` 的常量池项依然在，后面再怎么处理也已经带着它了。
2. `PreventNullAnalysisRemover.java:47` 也用 `FixedClassWriter(reader, 0)`。题面只说"probably affected"，请核实并一并处理。
3. `SneakyThrowsRemover.java:49` 用的是裸 `ClassWriter`，没有 `FixedClassWriter` 的 `getCommonSuperClass` 兜底。改 writer 的创建方式时，要看清这个差异是否应该保留。
4. `FixedClassWriter` 只有带 `ClassReader` 的构造器。要判断是否需要新增不带 reader 的构造路径。

B. 题面没给例子、但可能被检查的输入
1. 同一个类里有多个方法、多处 `sneakyThrow`，其中有些没有被 `throw` 吃掉。后一种情况下，`handleQueue` 会把调用写回去并发出警告，此时类里必须仍然保留 `Lombok.sneakyThrow`。
2. 类里没有任何会被去除的调用，此时 `changesMade` 为 false，返回 null。这条路径的行为不能变。
3. 带异常表、`StackMapTable`、泛型签名、注解、内部类、字段、`SourceFile`、`LineNumberTable` 等属性的类。丢掉"沿用原常量池"的优化之后，这些信息必须完整保留，文件仍须可加载、可通过验证。
4. 类里还有其他对 `lombok/*` 的引用，比如注解或 `@Generated`。题面期望的是不再有 `sneakyThrow` 的痕迹，别误删这类引用，也别因此误判测试失败。

C. 仓库已有的约定、测试
1. 看 `test/bytecode/src/lombok/bytecode/TestPostCompiler.java`、`RunBytecodeTests.java`、`TestClassFileMetaData.java` 和 `test/bytecode/resource/PostCompileSneaky.java`。现有测试怎样断言"去除成功"，有没有已有的常量池检查辅助方法。新测试应沿用同样的风格。
2. 入口处的 `ClassFileMetaData.usesMethod(...)` 是靠解析常量池判断的。修复后，这个方法可以反过来用来验证输出里是否还含有 `sneakyThrow`。另外要注意，修复不能影响它对输入的判断。
3. `lombok.debugAsmOnly` 这个系统属性保留了 sneakyThrow 调用。这个分支的行为要保持不变。
4. 看一下 `doc/changelog.markdown` 之类的变更记录有没有按版本登记的惯例，有就跟着登记。

D. 提交前建议自测
1. 编译题面的 `Class.java`，对结果做 `javap -v`，确认常量池里没有 `sneakyThrow` 和 `lombok/Lombok`。
2. 对 `@PreventNullAnalysis` 的等价样例做同样检查。
3. 构造一个故意没有 `throw` 的 `sneakyThrow` 调用：确认调用仍被保留，也仍有警告；再确认含多个方法和 try/catch 的类，处理后仍能加载并执行。
