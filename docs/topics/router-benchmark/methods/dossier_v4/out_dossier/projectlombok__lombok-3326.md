# 档案：UtilityClass + 泛型方法 + 同名重载导致 javac NPE

说明：我只查证了 javac 的 handler 和测试资源，没有编译、也没有运行复现。下面标明"推测"的内容都未经验证。

## 【1 题面要点】
- 期望行为：下面的代码在 JDK 11/17/18/19 上不应让 javac 崩溃（NPE 出在 `Types.asSuper`，由 `Infer` 的 incorporation 阶段触发）。JDK 8 不崩。
- 复现代码：题面给了。`@UtilityClass class Converter`，含 `<T> T convertValue(Class<T>)`、`DTO convert(Object)`、`Object convert(DTO)`，以及非 static 的内部类 `class DTO {}`。
- 触发点：`convert(Object)` 里调用 `convertValue(DTO.class)`。
- 题面没有给期望输出，也没有给修法建议。
- 题面列出了"能让代码通过编译的小改动"，这是唯一的线索：
  - "`static` is added to the inner class `DTO`"
  - "one of the `convert` methods is renamed"
  - "`convertValue(DTO.class)` is replaced with just `null`"
  - "changing `Class<T>` to `Class`"
- 题面还说"I have seen a few NPE reports but all were connected with `val`, while this is not."

## 【2 相关代码】
- `src/core/lombok/javac/handlers/HandleUtilityClass.java:93` 的 `changeModifiersAndGenerateConstructor`。这是最可能要改的函数。
  - 它只修改 AST 的 `mods.flags`，给类加 `FINAL`、给成员加 `STATIC`。
  - 第 124-135 行处理内部类：`innerClassDecl.mods.flags |= STATIC`。
  - 随后取 `innerClassDecl.sym`，如果 `sym.type` 是 `ClassType`，就调用 `setEnclosingType(Type.noType)`（第 132 行）。这是 #3097 的修法。
  - 第 117-121 行对方法只改 `methodDecl.mods.flags`，不碰 `methodDecl.sym`。
  - 第 111-114 行对字段也只改 `mods.flags`。
- 推测：handler 运行时，符号（`ClassSymbol` / `MethodSymbol`）已经由 `Enter` / `MemberEnter` 建好。
  - 内部类 `DTO` 的 `sym.flags_field` 还没有 `STATIC`。它的类型状态也可能不一致，比如 `supertype_field`、`outer_field`，或是 `Type.noType` 与类型参数的组合。
  - 这些不一致会在 `asSuper` 里被碰到。
  - 目前没有任何代码同步符号，修法大概率是同步 `sym.flags_field`，或补全类型信息。这是推断，没有验证。
- `src/core/lombok/javac/handlers/JavacHandlerUtil.java:1257-1313`：已有直接操作 `ClassSymbol.members_field` 的先例，用的是反射的 `ClassSymbolMembersField.enter/remove`。仓库里有改符号表的现成做法。
- 同类文件里没有其他地方改 `flags_field`（grep 无结果）。

## 【3 并列与牵连】
- Eclipse 版 `src/core/lombok/eclipse/handlers/HandleUtilityClass.java:93-135` 逻辑平行（`modifiers |= AccStatic`）。ecj 没有 javac 的符号问题，这个 bug 看起来只在 javac，大概率不用改。
- delombok 走 javac 的 handler，所以会一起受影响。
- 只有一处调用点，成对的 `handle` → `changeModifiersAndGenerateConstructor`。
- 改 `STATIC` 的符号同步会影响所有 `@UtilityClass` 用法：
  - `test/transform/resource/before/UtilityClass.java` 里有 `InnerClass` 和 `InnerStaticClass`。
  - `UtilityClassInner.java` 等其他用例也会受影响。
- `HandleFieldDefaults` 依赖 `@HandlerPriority(-4096)`，要让它先看到 `static`，所以改动要保持这个顺序语义。

## 【4 现有测试与约定】
- 测试是源码比对型的，没有 javac 编译断言：
  - `test/transform/resource/before/*.java` 对应 `after-delombok/*.java` 和 `after-ecj/*.java`。
  - 由 `test/transform/src/lombok/transform/TestSourceFiles.java` 驱动，另有 `TestWithDelombok.java`、`TestWithEcj.java`。
  - 相关用例：`UtilityClass`、`UtilityClassInner`、`UtilityClassErrors`、`UtilityClassInAnonymousClass`、`UtilityClassOnRecord`。
  - `UtilityClassOnRecord.java:1` 带 `// version 14:` 头，说明 JDK 版本限定用这种头注释。
- 隐藏测试很可能新增一个 `before/UtilityClassGeneric*.java`（名字是推测），配套 `after-delombok` / `after-ecj` 文件。
  - 它会用题面的代码，期望输出是 delombok 后的 `static` 方法加私有构造器。
  - 有 NPE 的 javac 版本才会暴露，测试是否稳定复现取决于 JDK 版本。
- changelog 在 `doc/changelog.markdown:16`：`inner classes in @UtilityClass classes were broken in JDK9+. Issue #3097`。这是同类前例，用的是 `setEnclosingType`。
- 与题面期望没有冲突。没有外部规范决定行为，只有 javac 内部状态一致性。

## 【5 边界与隐含要求】
- 内部类是否 `static` 要保持不变：`InnerClass` 变为 static 后，`new InnerClass()` 必须仍能编译。
- 内部类之间互相嵌套时，也要正确处理：`UtilityInner.InnerInner.InnerInnerInner` 这样的多层嵌套。
- `DTO` 已经是 static 或是 interface / enum 时，不要重复修改或破坏。
- 方法符号的 `STATIC` 同步：
  - 重载解析会看 `MethodSymbol` 的 flags。
  - `convert(Object)` 与 `convert(DTO)` 两个重载，加上泛型推断，都会读取这些符号。
- JDK 8 到 19+ 之间 javac 内部字段不同（比如 `ClassType` 的字段、`Flags` 常量）：
  - 需要用反射，或用 `lombok.permit.Permit` 访问。
  - 仓库里已有 `Permit.getField` 的先例。
- `sym == null` 的情况：比如 handler 在符号还没建好时运行。第 130 行已有 `!= null` 判断，新增代码要保持这种防御。
- 题面只说了泛型 + 同名重载 + 非 static 内部类的组合，修复不应依赖这三者同时出现。

## 【6 改动规模】
- 预计 1 个主文件（`HandleUtilityClass.java`），2-3 处局部修改：
  - 同步内部类符号。
  - 可能同步方法符号。
  - 可能重置或补全类型字段。
- 另加 1-3 个测试资源文件，可能再加 changelog 一行。
- 没有新结构，也不贯穿多层。

## 【7 难点一句话】
难点是诊断，不是写代码：根因藏在 javac 内部符号和类型状态（`flags_field`、`ClassType` 字段）与 AST 修改不同步，必须靠推断或实际在 JDK 11+ 上复现，才能确定该同步哪一块；而改动本身很小，还要兼顾多个 JDK 版本的反射兼容。