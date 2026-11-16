我已查完相关代码，下面直接给出档案。

# 仓库档案：@SuperBuilder 不生成 Javadoc

## 【1 题面要点】
- 要求：给类加 `@SuperBuilder` 后，生成的 builder 方法要带 Javadoc，行为与 `@Builder` 一致。题面写的是 "with `@Builder` the javadoc is correctly generated"。
- 没有复现代码，没有期望输出，也没有修法建议。
- 只给了版本号 1.18.20。
- 没有指明是哪些方法缺 Javadoc。从 `@Builder` 的现有行为推断，最可能是字段上的 Javadoc 没有被复制到 builder 的 setter 上。

## 【2 相关代码】
**主要改动点：SuperBuilder 的 setter 生成函数。**
- `src/core/lombok/javac/handlers/HandleSuperBuilder.java:952` `generateSimpleSetterMethodForBuilder`
  - 第 968 行用 `HandleSetter.createSetter(...)` 建出 `newMethod`，第 969 行直接 `injectMethod`。
  - 中间没有任何 Javadoc 复制。
- `src/core/lombok/eclipse/handlers/HandleSuperBuilder.java:995` 同名函数
  - 第 1011 行 `createSetter`，随后 `injectMethod(job.builderType, setter)`，同样没有复制。

**参照实现：`@Builder`。**
- javac：`HandleBuilder.java:937-941`
  - `job.sourceNode.up().getKind() == Kind.METHOD` 时调用 `copyJavadocFromParam(bfd.originalFieldNode.up(), newMethod, bfd.name.toString())`。
  - 否则调用 `copyJavadoc(bfd.originalFieldNode, newMethod, CopyJavadoc.SETTER, true)`。
- `copyJavadocFromParam` 在 `HandleBuilder.java:946`，是 private 方法。
- eclipse：`HandleBuilder.java:1055-1059`，`copyJavadocFromParam` 在 1063。它需要 `TypeDeclaration td` 参数，并调用 `setDocComment(cud, type, to, ...)`。
- 公共工具：`JavacHandlerUtil.java:2262` 的 `CopyJavadoc` 枚举，以及 2334/2347 的 `copyJavadoc`。eclipse 对应 `EclipseHandlerUtil.java:2874`、2928-2955。

`HandleSuperBuilder` 已经通过 `import static ...HandlerUtil.*`（第 27 行）引入了 `copyJavadoc`，但没有引入 `CopyJavadoc` 枚举。

## 【3 并列与牵连】
- javac 和 eclipse 两个 `HandleSuperBuilder` 要同步改。
- `@Singular` 字段走 `singularData.getSingularizer().generateMethods(...)`（javac `HandleSuperBuilder.java:946`，eclipse 约 990）。`JavacSingularsRecipes` 和 `singulars/*.java` 里没有任何 Javadoc 相关代码（grep 为空）。如果题面范围包含 singular 的 add/addAll/clear 方法，那是另一处，`@Builder` 本身对此也没做。
- `@SuperBuilder` 只作用于类，不会出现 `@Builder` 那种 `sourceNode.up()` 是 METHOD 的分支，所以 `copyJavadocFromParam` 对它不需要。
- 其他生成方法没有 Javadoc：`builder()`、`build()`、`toBuilder()`、`self()`、构造器。`@Builder` 的 `after-delombok/BuilderJavadoc.java` 里 `build()` 也没有 Javadoc，所以这些大概不用处理。
- 改动会影响所有 `@SuperBuilder` 的 delombok 输出（对有 Javadoc 的字段）。所有含 Javadoc 字段的 SuperBuilder 测试资源都可能需要更新。

## 【4 现有测试与约定】
- `test/transform/resource/before/BuilderJavadoc.java` 和 `after-delombok/BuilderJavadoc.java` 是 `@Builder` 的 Javadoc 参考。
  - 字段有 `@param`、`@return`、`@see` 时，setter 得到：
    ```
    * basic gets only a builder setter.
    * @see #getsetwith
    * @param tag is moved to the setter.
    * @return {@code this}.
    ```
  - 字段上原来的 `@param` 被移走，`@return` 被去掉。
- `BuilderConstructorJavadoc` 是构造器上 `@Builder` 的对应测试。
- `test/transform/resource/before/SuperBuilder*.java` 里 grep "Javadoc" 为空，说明 SuperBuilder 目前没有任何 Javadoc 测试。
- 隐藏测试很可能是新增的 `SuperBuilderJavadoc` 之类的 before/after 资源（after-delombok，可能还有 after-ecj）。
  - 输出必须与 `@Builder` 的格式逐字一致：`{@code this}.`、`@param` 搬移、`@return` 去除。
  - 同时存在 `@Getter`/`@Setter` 的字段，要求 setter 与 getter 的 Javadoc 各取所需。
- 与题面没有冲突。

## 【5 边界与隐含要求】
- 字段上带 `@param`/`@return`/`@see` 或 `SETTER`/`GETTER` 分段时的剥离规则，已由 `CopyJavadoc.SETTER` 处理。
- `forceAddReturn=true`，会补上 `@return {@code this}.`。
- 字段没有 Javadoc 时不应出错。`copyJavadoc` 内部有 try/catch，并吞掉异常。
- 用户预先写了同名 setter 时（`predef`），生成会提前 return，不覆盖。这个逻辑在复制之前，不受影响。
- 复制必须发生在 `injectMethod` 之前。
- eclipse 侧需要 `TypeDeclaration`。可以用 `td`，即 `job.builderType.get()`。注意 `@Builder` 的 eclipse 路径用的 `td` 是哪一个，要对照确认。
- 如果测试同时跑 eclipse（after-ecj），要确认 eclipse 能产出等价的 Javadoc。
- 继承场景下父类字段不在本类处理，不涉及。
- 要不要更新 `doc/changelog.markdown`（第 5 行附近有 BUGFIX 条目格式）。

## 【6 改动规模】
- 约 2 个源文件，各 1 处：javac 与 eclipse 的 `generateSimpleSetterMethodForBuilder`。每处只需加 1 行 `copyJavadoc(...)`，外加一个 import。
- 另加 1 处 changelog 和若干测试资源（before、after-delombok，可能还有 after-ecj）。
- 是局部修补，不需要新增结构。

## 【7 难点一句话】
改动本身只有两行（在两个 `generateSimpleSetterMethodForBuilder` 里补 `copyJavadoc(originalFieldNode, newMethod, CopyJavadoc.SETTER, true)`），难在两点：一是 eclipse 侧签名需要 `TypeDeclaration`，二是隐藏测试可能要求与 `@Builder` 逐字一致的 Javadoc 输出，包括 singular 等边缘字段。后一点没有测试资源可对照，只能靠推断。