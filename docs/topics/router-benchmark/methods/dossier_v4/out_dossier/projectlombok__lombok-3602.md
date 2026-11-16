我已经查完相关代码和测试，下面是档案。

## 仓库档案：SneakyThrows / PreventNullAnalysis 后处理残留 lombok 常量池条目

**【1 题面要点】**
- 要求的行为：`@SneakyThrows` 编译后的 class 文件里不应再有 `lombok.Lombok.sneakyThrow` 的痕迹。
- 现状：方法体里的调用已被移除，但常量池里仍留着 Methodref、Class `lombok/Lombok`、NameAndType、Utf8 `sneakyThrow` 以及描述符等条目。
- 题面给出的原因：`new ClassWriter(reader, 0)` 会复用原 class 的常量池。
- 题面点名 `PreventNullAnalysis` 可能同样受影响。
- 期望输出（照抄）：“There are no references to sneakyThrow in the class file.”
- 题面给了复现步骤（`Class.java` 加 `javap -v`）。没有给修法，只给了根因线索。

**【2 相关代码】**
- `src/core/lombok/bytecode/SneakyThrowsRemover.java:43-186`
  - `applyTransformations` 先用 `usesMethod("lombok/Lombok","sneakyThrow")` 判断，再调用 `fixJSRInlining`。
  - 第 49 行 `new ClassWriter(reader, 0)` 是关键。这里的 `reader` 传入 writer 构造器，会复制原常量池。
  - 内部 `SneakyThrowsRemoverVisitor`（53-178）把调用先排队，紧跟 ATHROW 时丢弃。
- `src/core/lombok/bytecode/PreventNullAnalysisRemover.java:41-77`
  - 第 47 行 `new FixedClassWriter(reader, 0)`，同样把 reader 传给 writer。
  - 第 56-68 行 `visitMethodInsn` 直接丢弃 `preventNullAnalysis` 调用。
- `src/core/lombok/bytecode/AsmUtil.java:36-48`
  - `fixJSRInlining` 第 38 行也是 `new FixedClassWriter(reader, 0)`。它在两个 remover 前被调用，会先把原常量池整个带进中间字节码。
- `src/core/lombok/bytecode/FixedClassWriter.java:27-42`
  - 只重写 `getCommonSuperClass`，构造器签名是 `(ClassReader, int)`。

**【3 并列与牵连】**
- 一共有 3 处“reader 传给 writer”的构造：两个 remover 加 `AsmUtil.fixJSRInlining`。
  - 只改 remover 不够。`fixJSRInlining` 的输出已带着完整旧常量池，之后 remover 的 `ClassReader` 读到的就是这份。
  - 如果 remover 改成不传 reader，`fixJSRInlining` 的输出会被重新读一遍，再写进全新常量池，此时 `fixJSRInlining` 本身可以不改。
  - 如果只改 `fixJSRInlining` 不改 remover，同样残留。
- `FixedClassWriter` 只被这三处使用。`SneakyThrowsRemover` 用的是裸 `ClassWriter`，没有 `getCommonSuperClass` 的兜底。
  - 不传 reader 后 writer 的 flags 仍是 0（不计算 frames/maxs），所以通常不触发 `getCommonSuperClass`。
- 改成不传 reader 后，ASM 不再对方法体做原始字节拷贝优化，会走完整的 visit 路径。影响所有被这两个 remover 处理的 class，只在含 sneakyThrow / preventNullAnalysis 调用时触发。
- `PostCompiler` 链上还有其他 `PostCompilerTransformation`，这次没有逐个查，但这两个 remover 是用 ASM 重写的主要实现。

**【4 现有测试与约定】**
- `test/bytecode/src/lombok/bytecode/TestPostCompiler.java:47-52`：
  - 断言前置条件：`new ClassFileMetaData(compiled).usesMethod("lombok/Lombok","sneakyThrow")` 为 true。
  - 断言 `assertNotSame(compiled, transformed)`。
  - 断言 `transformed.length < compiled.length`。
  - 全程 `DiagnosticsReceiver` 收到 warning/error 就 `fail`。
  - 现有测试没有断言转换后不再含 lombok 引用。
- 资源：`test/bytecode/resource/PostCompileSneaky.java:3` 是 `throw lombok.Lombok.sneakyThrow(new Exception());`。
- `ClassFileMetaData`（`src/core/lombok/bytecode/ClassFileMetaData.java`）已有可供隐藏测试使用的断言方法：
  - `usesMethod`（202/223）
  - `usesClass`（173）
  - `containsUtf8`（160）
- 隐藏测试很可能是：转换后 `usesMethod("lombok/Lombok","sneakyThrow")` 为 false，或者 `usesClass("lombok/Lombok")` / `containsUtf8("lombok/Lombok")` 为 false。
- 没有发现与题面冲突的约定。`lombok.debugAsmOnly` 属性（SneakyThrowsRemover:67，PreventNullAnalysisRemover:64）会保留调用，属于调试开关。

**【5 边界与隐含要求】**
- `PreventNullAnalysisRemover` 目前没有测试，也没有对应的资源文件。
- 调用若没有被 `throw`，`handleQueue` 会把调用重新写回（SneakyThrows:79-82）。这时常量池里必须仍有它，不能误删。
- 同一个 class 里其他方法可能仍合法引用 lombok，例如没被 throw 的情况或用户自己的 lombok 调用，所以不能按“全文件剥离 lombok”来处理。
- 重建常量池后要保持字节码合法：
  - 带 `StackMapTable` 的 Java 7+ class 要能正确读写。
  - 旧版本 class 里的 JSR/RET 由 `fixJSRInlining` 处理。
  - 去掉 reader 复用后，frames 通过 `visitFrame` 照常重写，但 flags=0 时仍需保证 frames 原样透传。
- 大小断言：新常量池更小，`length < compiled.length` 应该仍成立。
- 属性、注解、InnerClasses 等非方法内容经过完整 visit 后应保持不变。这点要靠回归测试确认，我没有实测。

**【6 改动规模】**
- 核心改动很小，只涉及 3 个文件 3 处：`SneakyThrowsRemover:49`、`PreventNullAnalysisRemover:47`、`AsmUtil:38`。
- 把 `new (Fixed)ClassWriter(reader, 0)` 改成不带 reader 的写法。`FixedClassWriter` 可能需要新增一个只接收 flags 的构造器。
- 另外需要补测试：更新 `TestPostCompiler`，最好再为 `PreventNullAnalysis` 增加资源和用例。
- 属于局部修补，不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
改动本身只是去掉 `ClassWriter` 构造器里的 `reader` 参数，真正容易出错的是找全三处（尤其是容易漏掉的 `fixJSRInlining`），并确认丢掉“复用常量池”这个优化后 class 文件仍然合法。