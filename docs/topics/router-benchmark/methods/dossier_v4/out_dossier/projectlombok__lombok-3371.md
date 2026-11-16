# 仓库档案：record 上 `byte @NonNull[] bytes` 不生成空检查

注意：下面的结论来自静态阅读，我没有运行任何测试。第 2 点的根因是我从代码路径推出来的，没有用实际输出验证。

## 【1 题面要点】
- **要求的行为**：record 组件写成 `byte @NonNull[] bytes`（类型注解、基本类型数组）时，规范构造器也要生成 `bytes == null` 的空检查并抛 NPE。
- **复现**：题面给了 `NamedByteArray` record 和 JUnit 测试。`new NamedByteArray("name", null)` 应抛 NPE。
- **期望输出**：题面只有反编译结果，里面只有 `name` 的检查，没有 `bytes` 的检查。
- **修法建议**：没有。
- **关键句**："@NonNull should throws NPE on primitive array field on a record if it is null."
- **版本**：Lombok 1.18.26，Java 19。
- **对照**：`@NonNull String name` 的检查已经生成，说明问题只出在类型注解放在数组上这一种写法。

## 【2 相关代码】
- `src/core/lombok/javac/handlers/HandleNonNull.java:219` 的 `handle(...)`：
  - **字段分支**（221–243）：`annotationNode.up().getKind()==FIELD` 时，对带 RECORD 标志的字段补紧凑构造器并加空检查。
  - **其余分支**（245–279）：靠 `switch(annotationNode.up().getKind())` 分发。`ARGUMENT` 直接作为参数；`TYPE_USE` 取 `directUp().directUp()` 作为 `paramNode`；其他一律 `return`。
- `HandleNonNull.java:74` 的 `createRecordArgslessConstructor`：生成紧凑构造器。
- `HandleNonNull.java:117` 的 `addCompactConstructorIfNeeded`：按需创建紧凑构造器。
- `HandleNonNull.java:163` 的 `addNullCheckIfNeeded`：插入检查，并对基本类型警告。
- `src/core/lombok/javac/JavacAST.java:328–388`：
  - `buildField` 先挂 `mods.annotations`，再对 `vartype` 调 `buildTypeUse`。
  - `buildTypeUse` 对 `JCAnnotatedType`、`JCArrayTypeTree` 等建 `TYPE_USE` 节点，它们的父节点是 FIELD 或嵌套的 TYPE_USE 节点。
- Eclipse：`src/core/lombok/eclipse/handlers/HandleNonNull.java`：
  - `handle`（219）：diet parse 阶段加紧凑构造器。
  - `handle0`（251）：完整解析阶段加检查。
  - `addCompactConstructorIfNeeded`（107）、`findCompactConstructor`（241）。
  - `handle0` 的 `TYPE_USE` 分支在 290–300 行。
- 基本类型判断：
  - `src/utils/lombok/javac/Javac.java:143`：`isPrimitive(JCExpression)` 用 `ref.toString()` 加正则 `^(?:boolean|byte|…)$`（`JavaIdentifiers.java:61`）。
  - `src/utils/lombok/eclipse/Eclipse.java:173`：`dimensions()>0` 时返回 false。
- 空检查生成：`JavacHandlerUtil.java:1806`（`typeNode != null && isPrimitive(typeNode)` 时返回 null）、`EclipseHandlerUtil.java:2198`。

**根因推测**：
- `byte @NonNull[]` 的注解不在 `field.mods.annotations`，而在 `vartype` 的 `JCAnnotatedType` 里。lombok 把它建成 `TYPE_USE` 节点的子 ANNOTATION，所以走不进 `up()==FIELD` 的 record 分支。
- 进入 `TYPE_USE` 分支后，`paramNode` 是字段或类型节点，不是 `ARGUMENT`，`paramNode.getKind()!=ARGUMENT`（260 行）就 `return` 了。
- `@NonNull String name` 是声明注解，直接挂在字段上，所以能工作。
- 我没确认 javac 是否对 record 组件的数组类型注解也把它同步到字段的 `mods.annotations`。题面反编译里 `byte @NonNull []` 在参数上保留，说明类型注解确实留在类型上。

## 【3 并列与牵连】
- **javac 与 Eclipse 两套实现要同步改**。Eclipse 的 `TYPE_USE` 分支（290–304 行）有同样的 `paramNode` 取法，之后要求是 Argument，record 字段同样不会走通。
- **非 record 字段与方法参数**：`NonNullTypeUse.java` 覆盖了 `String @NonNull [][][]` 这类参数写法，改 `TYPE_USE` 分支会影响它们。
- 类型注解在 record 组件上的处理，还可能牵连 `HandleConstructor`、`HandleSetter` 等读取字段 `@NonNull` 的地方，它们按名字匹配注解。
- `generateNullCheck` 的 `isPrimitive` 判断被所有 `@NonNull` 生成路径共用，如果改它，会影响 setter、构造器、`@Builder` 等。
- Eclipse 要考虑两阶段：diet parse 只能生成构造器，完整解析才能改方法体。

## 【4 现有测试与约定】
- 测试是文件对：`test/transform/resource/before/NonNullOnRecord.java`、`NonNullOnRecord2/3`、`NonNullExistingConstructorOnRecord`，配 `after-delombok/` 和 `after-ecj/` 的期望输出。
- `before/NonNullOnRecord.java:5`：`public record NonNullOnRecord(@NonNull String a, @NonNull String b) {}`，没有任何类型注解或数组的记录用例。
- `NonNullOnRecord3`：显式长形式构造器，期望不再重复生成。
- `before/NonNullTypeUse.java:5-17`：参数上 `@NonNull String[][][]` 和 `String @NonNull [][][]` 等，是类型注解的现有约定，没有 record 版本。
- **与题面冲突**：基本类型数组的 `@NonNull` 本来就应该生效，因为数组是引用类型。目前我没看到仓库约定把它当"meaningless on primitive"来排除，但 javac 路径的 `isPrimitive` 用字符串匹配，对 `byte[]` 返回 false，这个判断本身看起来是对的。
- 我没有读到 `after-*` 里与 `byte @NonNull[]` 相关的期望文件，也没找到 record 加类型注解的 before 文件。隐藏测试很可能新增类似 `NonNullOnRecord4` 的文件对。

## 【5 边界与隐含要求】
- 注解在数组维度上的位置：`byte @NonNull [] x`、`byte[] @NonNull [] x`，以及 `@NonNull byte[] x`（声明注解）。要保证只有注解在最外层数组类型上才生成检查，里层维度不能触发。
- 非数组的基本类型 `@NonNull int x` 仍应警告并且不生成检查。
- 引用类型上的类型注解：`java.lang.@NonNull String`、`List<@NonNull String>`，不能因此误给整个组件加检查。
- 同一组件上同时有声明式和类型式 `@NonNull`，不能重复生成两次检查（`addNullCheckIfNeeded` 的去重逻辑会处理一部分）。
- 显式紧凑构造器或长形式构造器的现有行为不能变。
- Eclipse（ecj）和 javac 两个输出都要满足 `after-*` 期望。
- 异常类型配置 `lombok.nonNull.exceptionType`、警告 `@NonNull is meaningless on a primitive.` 的行为保持不变。

## 【6 改动规模】
- 预计 2 个核心文件：javac 与 Eclipse 的 `HandleNonNull.java`，各改 1 到 3 处。可能还要动 `JavacAST.java` 或 `JavacHandlerUtil` 里的小工具。
- 新增测试资源：`before/`、`after-delombok/`、`after-ecj/` 三个文件。
- 属于局部修补，不需要新增结构，但要读懂 AST 节点结构。

## 【7 难点一句话】
难点在于定位类型注解（`byte @NonNull[]`）在 javac 和 Eclipse 的 AST 里分别挂在哪、在 `TYPE_USE` 分支里如何识别"这是 record 组件的最外层数组类型注解"，并让两个编译器都生成同样的检查。我只静态读了代码，没有运行验证。