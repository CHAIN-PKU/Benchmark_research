**档案：ExtensionMethod 误处理无关方法调用（javac）**

**【1 题面要点】**
- 要求的行为：`@ExtensionMethod` 不应改写与扩展无关的方法调用。例子里 `"foo".startsWith("f")` 是正常的 `String` 方法调用，不应被改写。
- 复现：`@ExtensionMethod({java.lang.String.class, Bug.Extension.class})`，其中把 `String.class` 当成扩展提供者，`Extension` 是空类。
- 报错：`Bug.java:8: error: incompatible types: String cannot be converted to int`，指向 `startsWith`。
- 期望输出：题面没写，隐含是正常编译通过。
- 修法建议：没有。题面只有复现和报错，没有给出原因分析。
- 环境：JDK 17、Gradle 插件 6.6，所以是 javac 路径。

**【2 相关代码】**
- `src/core/lombok/javac/handlers/HandleExtensionMethod.java:114-125` 的 `getExtension` 负责收集提供者类里的扩展方法。
  - 第 120 行 `if ((method.flags() & (STATIC | PUBLIC)) == 0) continue;` 是最可能的根因。
  - 这个按位与只要 STATIC 或 PUBLIC 任意一个标志存在，结果就非 0，等于没有过滤。
  - 所以 `String` 的 public 实例方法，如 `startsWith(String,int)`、`indexOf(String,int)`，都被当成扩展方法收进来。
  - 第 121 行只过滤了无参方法。
- `HandleExtensionMethod.java:159-209` 的 `handleMethodCall` 负责改写调用。
  - 第 178 行：`suppressBaseMethods` 默认 true 时，不管原调用是否解析成功，都继续往下走。
  - 第 196-207 行：按方法名和第一个参数类型匹配，一匹配就把 `receiver` 前置到参数列表，并把 `meth` 改成 `Provider.method`。
  - 具体到本例：`startsWith(String,int)` 的首参是 `String`，接收者 `"foo"` 可赋值给它，于是被改写成 `String.startsWith("foo","f")`，第二个参数 `"f"` 不是 int，报错。
- 第 117 行 `tsym.getEnclosedElements()` 是遍历来源。

**【3 并列与牵连】**
- Eclipse 路径 `src/eclipseAgent/lombok/eclipse/agent/PatchExtensionMethod.java:225-228` 已经分别判断 `isStatic()` 和 `isPublic()`，所以这个 bug 只出在 javac。Eclipse 那边没有对应问题，这是它与 javac 的不一致点。
- `getExtension` 只在 `getExtensions` 里被调用，没有第二个调用点。
- 一个小牵连：现在 `(STATIC|PUBLIC)==0` 把“仅 static 非 public”或“仅 public 非 static”的方法都放行了。修正后只收 public static 方法，可能会让极少数依赖旧行为的用法不再生效。
- delombok 和 javac 共用 `HandleExtensionMethod`，所以修这一处两者都会改变。

**【4 现有测试与约定】**
- 测试用 `test/transform/resource/before` 加 `after-delombok` 和 `after-ecj` 的文件对比。
- 现有的 `ExtensionMethod*.java` 里，提供者方法全是 `public static`，例如 `ExtensionMethodPlain.java:13-18` 的 `Extensions`。
- `ExtensionMethodSuppress.java:35-43` 的 `Extensions` 也是 `public static`，没有测试用到非 static 的提供者方法。
- 现有测试没有用 JDK 类（`String.class`）做提供者的例子。
- 约定：Eclipse 实现要求 static 且 public，文档也说扩展方法是静态方法，与题面期望不冲突。
- 隐藏测试很可能新增一个 `ExtensionMethod*.java` 的 before 文件，加 after-delombok 和 after-ecj 的期望输出，内容类似“提供者含实例方法 / 用 `String.class`”。

**【5 边界与隐含要求】**
- 需要同时要求 static 且 public，不能只检查其一。
- 提供者的实例方法不能作为扩展方法，但同名的真正静态扩展方法仍要工作。
- 如果新增 after-ecj 的测试文件，要确认 Eclipse 路径的输出与 delombok 一致。
- 接口和注解已在第 107 行被过滤。
- 接口里的 static 方法的 flags 是否带 PUBLIC，题面没涉及。
- 提供者类里的 private static 或 package-private static 方法也不应被当成扩展，修正后会自然被排除。
- 父类里继承来的方法不在 `getEnclosedElements` 里，这个行为不变。

**【6 改动规模】**
- 核心修复只有 `HandleExtensionMethod.java` 一个文件的一行，把 `== 0` 改成要求两个标志都在。
- 另外加测试资源（before 加 after-delombok，可能还有 after-ecj），以及可能的 changelog 一行。
- 属于局部修补，不涉及新结构。

**【7 难点一句话】**
代码改动极小，难在定位：报错表面看像 `startsWith` 被误改写，要追到第 120 行的位运算过滤条件写错（`== 0` 应为要求 STATIC 和 PUBLIC 都在）。一旦找到，修复很直接。