**仓库档案：@ExtensionMethod 用于 record**

**【1 题面要点】**
- 要求的行为：`@ExtensionMethod` 能用在 `record` 上，用 maven/javac 构建不报错。Eclipse 已经允许，javac 不允许，要让两边一致。
- 题面给了复现，但没有期望输出。报错原文是：`@ExtensionMethod can only be used on a class or an enum or an interface`。
- 复现代码：`@ExtensionMethod(String.class) public record MyRecord(String foo, String bar) { String baz() { return "\n".join(foo, bar); } }`。
- 期望："I can use `mvn` to build"，即 record 内的扩展方法调用要被改写成静态调用。
- 题面没有给修法建议。

**【2 相关代码】**
- `src/core/lombok/javac/handlers/HandleExtensionMethod.java:71-96`：`handle()` 是 javac 的入口。
  - 第 76 行调用 `isClassOrEnumOrInterface(typeNode)`，第 78-81 行在不满足时报题面里的错误并 return。
  - 其后是 `getExtensions`（99）、`new ExtensionMethodReplaceVisitor(...).replace()`（93）。
- `src/core/lombok/javac/handlers/JavacHandlerUtil.java:2125-2127`：`isClassOrEnumOrInterface` 的实现是 `isClassAndDoesNotHaveFlags(typeNode, ANNOTATION | RECORD)`。**RECORD 标志被明确排除，这就是直接原因。**
  - 同文件还有 `isClassEnumOrRecord`（2132，排除 INTERFACE|ANNOTATION）、`isRecord`（2139）、`isClassAndDoesNotHaveFlags`（2143）。
  - 全仓库只有 javac 的 `HandleExtensionMethod` 调用 `isClassOrEnumOrInterface`，其他地方都不用它。
- `src/core/lombok/eclipse/handlers/HandleExtensionMethod.java:44-65`：Eclipse 的 handler 只做错误检查。
  - 第 52-53 行只排除 `AccAnnotation`，所以 record 在 Eclipse 下本来就通过。
  - 错误文案是 "legal only on classes and enums and interfaces."（第 56 行）。
  - 真正的改写在 `src/eclipseAgent/lombok/eclipse/agent/PatchExtensionMethod.java`（`resolveType` 在 254 行附近），在 agent 里完成。

**【3 并列与牵连】**
- 并列实现：javac 和 Eclipse 各有一个 `HandleExtensionMethod`。Eclipse 侧已放行 record，只有错误文案没提 record。
- 改 `isClassOrEnumOrInterface` 或改它的调用点影响很小，因为唯一调用者就是 javac 的 `HandleExtensionMethod`。
- 不能乱动同类工具方法：`isClassOrEnum`、`isClass` 被 Getter、ToString、Constructor 等大量使用，且它们有意排除 record。
- `ExtensionMethodReplaceVisitor` 是内部类（`HandleExtensionMethod.java` 130 行以后），我没细读。它遍历类体改写方法调用，需要确认它对 record 的类体、record 的 compact constructor 和自动生成成员没有特殊处理。
- 文档 `src/core/lombok/experimental/ExtensionMethod.java` 的 javadoc、`website` 的文档以及 `doc/changelog.markdown` 可能需要同步，但不影响测试。

**【4 现有测试与约定】**
- 转换测试在 `test/transform/resource/before|after-ecj|after-delombok/ExtensionMethod*.java`，共 12 个用例。
  - 例如 `before/ExtensionMethodPlain.java:3-4` 用的是 `@ExtensionMethod({java.util.Arrays.class, ...}) class ExtensionMethodPlain`，**目前没有 record 用例**。
  - 隐藏测试很可能新增一个 `ExtensionMethodOnRecord.java`（或类似名字），放在 before、after-ecj、after-delombok 三个目录里。
- 其他 record 用例的约定（如 `SynchronizedInRecord.java`、`WithOnRecord.java`）：文件首行写 `// version 14:`，限定只在 JDK 14 及以上运行。
- 约定：record 相关标志用 `RECORD`（javac）和 `isRecord`（Eclipse，`EclipseHandlerUtil.java:2753`）。
- 与题面期望不冲突。题面要求放开，Eclipse 行为已是参照。
- 外部规范：Java 语言里 record 是隐式 final 的类，可以声明方法，所以接受 `@ExtensionMethod` 是合理的。

**【5 边界与隐含要求】**
- 错误文案可以顺带改成包含 record（javac 和 Eclipse 两边），但不要破坏现有测试对文案的断言。我没找到断言该文案的测试，不确定。
- javac 的编译器版本在 JDK 14 以下没有 `RECORD` 标志，用到 record 的测试要带 `// version 14:`。
- 要确认 record 类体内的方法调用（如 `baz()` 里的 `"\n".join(foo, bar)`）能正常解析并改写，包括调用 record 组件字段 `foo`、`bar`。
- 嵌套 record、局部 record、以及 record 内再嵌套类上的注解，也应该走同一条路径。
- 注解解析：record 声明上的注解处理顺序（HandlerPriority 66560，要晚于 `HandleVal`）不受影响。

**【6 改动规模】**
- 最小改动是 1 个文件的 1 处：`JavacHandlerUtil.java:2126` 去掉 `RECORD` 排除，或者改 `HandleExtensionMethod.java:76` 的判断。
- 外围改动：新增 2-3 个测试资源文件，可选地改错误文案。
- 属于局部修补，不需要新增结构。

**【7 难点一句话】**
- 判断本身很容易（去掉 RECORD 排除），难点只在两处。
  - 其一是确认 `ExtensionMethodReplaceVisitor` 在 record 里不会出问题。我没读完这个 visitor，这一点未验证。
  - 其二是隐藏测试可能要求 after-delombok/after-ecj 的输出格式（record 的 delombok 打印）完全匹配，这取决于测试框架，不取决于改动本身。