**档案：Jakarta `@Nonnull`/`@Nullable` 支持**

查证说明：下文行号均来自实际阅读。我没有跑构建或测试，也没有复现 issue。

**【1 题面要点】**
- 要求的行为：`@Builder` 生成的 builder 方法，要把字段上的 `jakarta.annotation.Nullable` 复制到参数上。
- 期望输出：`public JakartaExample.JakartaExampleBuilder first(@Nullable final List<String> first)`。
- 复现：有。给了 `@Value @Builder` 加 `@Nullable List<String> first` 的类，以及 `lombok.addNullAnnotations = CUSTOM:jakarta.annotation.Nonnull:jakarta.annotation.Nullable`。
- 修法建议：没有。
- issue 里的两个观察，都与代码一致：
  - 返回值上的注解能出现。这是 `addNullAnnotations` 的作用。
  - javax 和 checker 的注解总会被复制，与该配置无关。这是内置的固定列表。
- 标题是 "Support Jakarta Nonnull/Nullable annotations"，所以 `jakarta.annotation.Nonnull` 也应一并支持。

**【2 相关代码】**
- `src/core/lombok/core/handlers/HandlerUtil.java:82-120`：`NONNULL_ANNOTATIONS` 列表。里面出现在 javax 的是第 106 行 `"javax.annotation.Nonnull"`。出现在这个列表里的注解会触发生成 null 检查。
- `HandlerUtil.java:130-195`：`BASE_COPYABLE_ANNOTATIONS` 列表。javax 条目在 163-166 行：`CheckForNull`、`Nonnull`（重复写了两次，165 行）、`Nullable`。
- `HandlerUtil.java:424`：`COPY_TO_SETTER_ANNOTATIONS`。
- `HandlerUtil.java:122-129` 的注释说明了维护规则：
  - 凡是语言级的 nullity 注解，都由 lombok 自己维护进 `BASE_COPYABLE_ANNOTATIONS`。
  - `NONNULL` 列表里的每一项，原则上也应该在 copyable 列表里。
  - 注释写着"When in doubt, leave it out"，同时给了用户配置路径 `lombok.copyableAnnotations`。
- 这两个列表里**没有任何 `jakarta` 条目**。我在整个仓库搜过 `jakarta`，没有任何匹配，但搜索时用了 `!*.{jar,html,js}` 的排除 glob。
- 最小修改点就在这个文件。
- `src/core/lombok/core/configuration/NullAnnotationLibrary.java:65-74`：预置库 `JAVAX`、`ECLIPSE` 等，内含 `custom(...)`。目前没有 `JAKARTA` 条目。
- `custom(...)` 写在第 98-104 行。`CUSTOM:` 的解析在这个文件第 114 行之后，我没有读到。
- 两个使用列表的位置：
  - javac 在 `src/core/lombok/javac/handlers/JavacHandlerUtil.java:1672-1692`。`hasNonNullAnnotations` 遍历 `NONNULL_ANNOTATIONS`。
  - javac 在 `JavacHandlerUtil.java:1697-1739`。`findCopyableAnnotations` 先查配置的 `COPYABLE_ANNOTATIONS`，再查 `BASE_COPYABLE_ANNOTATIONS`。
  - eclipse 对应 `src/core/lombok/eclipse/handlers/EclipseHandlerUtil.java:790/800/826`，同样的结构。

**【3 并列与牵连】**
- 并列实现：javac 与 eclipse 两套 handler 都读同一份 `HandlerUtil` 列表。只改列表即可同时覆盖两边，handler 本身不用动。
- 成对项：`Nonnull`/`Nullable`、`CheckForNull`。Jakarta 对应的类是 `jakarta.annotation.Nonnull`、`jakarta.annotation.Nullable`。
- 我没有核实 Jakarta 是否还有 `CheckForNull`，需要自己确认。
- 加入 `NONNULL_ANNOTATIONS` 的牵连：lombok 会在 setter 和构造器里为带 `jakarta.annotation.Nonnull` 的字段生成 null 检查。这是行为变化，不只是"复制注解"。这与 javax 的现有处理一致。
- 复制范围：`@Getter`、`@Setter`、`@With`、`@Builder`、`@Singular` 的 builder 方法，都使用 `BASE_COPYABLE_ANNOTATIONS`。
- 文档：`website/templates/features/GetterSetter.html:70` 列了 `javax.annotation.Nonnull` 作为例子。`doc/changelog.markdown` 顶部是未发布版本 v1.18.27，可在那里加一条。

**【4 现有测试与约定】**
- 测试资源在 `test/transform/resource/`，分 `before/`、`after-delombok/`、`after-ecj/` 三个目录。
- 与 null 注解相关的有 `NullLibrary1`、`NullLibrary2`（`//CONF: lombok.addNullAnnotations = eclipse`）、`EqualsAndHashCodeWithOnParam`、`BuilderSingularNullBehavior1`、`EqualsAndHashCodeWithNonNullByDefault`。
- 测试用的注解 stub 放在 `test/stubs/`，目前只有 `com`、`java`、`org`，没有 `javax`，也没有 `jakarta`。例如 `test/stubs/org/checkerframework/checker/nullness/qual/Nullable.java`。
- 隐藏测试大概率要新增 `jakarta.annotation.*` 的 stub，以及一个 `before/after` 样例。stub 是测试侧的东西，实现者可能需要自己补，否则样例编译不过。
- `test/core/src/lombok/RunTestsViaEcj.java:244` 把 `build/teststubs` 加入 classpath。stub 的编译配置在 `buildScripts/compile.ant.xml`，我没有读到测试 stub 的那一段。
- 我没有找到专门为 javax `Nullable` 复制到 builder 的断言，所以没有现成的断言可以引用。
- 与题面不冲突。仓库的约定允许 lombok 内置 copyable 列表，只是对新增项很谨慎。

**【5 边界与隐含要求】**
- `jakarta.annotation.Nonnull` 也该加入两个列表，否则会漏掉非空侧。
- 是否把 jakarta 的 `CheckForNull` 等一起加：需要确认它是否存在，我没有查。
- `JAVAX` 之外要不要新增 `JAKARTA` 预置库：这会让 `lombok.addNullAnnotations = jakarta` 可用。issue 没有要求，但 `ConfigurationKeys.java:105` 的文档列表需要同步更新。
- 配置值大小写：`valueOf` 里做了 `toLowerCase`（第 115 行）。这与 `CUSTOM:` 的大小写处理有关，我没有读完它。
- 重复项：165 行 `javax.annotation.Nonnull` 重复，属于无害的既有问题。
- `typeMatches` 同时按全名和简单名匹配（需要 import）。jakarta 类名与 javax 同名，所以 `@Nullable` 靠 import 区分。这一点我没有验证。

**【6 改动规模】**
- 最小修复：1 个文件（`HandlerUtil.java`），2 处，各加 1-2 行。
- 完整一些：加预置库、更新文档和 changelog，另加 stub 与测试样例，共约 5-7 个文件。
- 都是局部修补，不需要新增结构，也不用改 javac 与 eclipse 的 handler。

**【7 难点一句话】**
代码本身很简单（往两个列表里加几项），难点在于不看上游就判断要加哪些条目，以及测试需要 `jakarta` stub 和 javac/ecj 两套期望输出。