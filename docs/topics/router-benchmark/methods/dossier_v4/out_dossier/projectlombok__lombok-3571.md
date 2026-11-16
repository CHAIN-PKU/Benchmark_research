我已经查证了 javac 和 Eclipse 两侧的 HandleBuilder 与工具方法，下面直接给档案。

# 仓库档案：@Builder 嵌套 record + 泛型外围类

## 【1 题面要点】
- 要求的行为：外层类带泛型（`Reproducer<T>`）时，嵌套的 `record NestedRecord(String value)` 不写 `static`，加 `@Builder` 也要能编译。
- 实际现象：javac 报 `non-static type variable T cannot be referenced from a static context`。题面推测是"生成的 builder 被错误地带上了外围类的泛型"。
- 复现：有最小样例（上面的 Reproducer）。
- 期望输出：只有 "No need to explicitly mark records as static as they are such by the definition"。没有给期望的生成代码，也没有给修法建议。
- 题面还提到 #3140（类似问题），版本 1.18.24，javac 17。

## 【2 相关代码】
- `src/core/lombok/javac/handlers/JavacHandlerUtil.java:2034-2063`：`namePlusTypeParamsToTypeReference` 的几个重载。
  - 2036 和 2042：`instance = (td.mods.flags & Flags.STATIC) == 0`，只看显式 STATIC 标志。嵌套 record 没写 `static` 时，这里会得出 instance=true。
  - 2054：`outerInstance = instance && ((td.mods.flags & Flags.STATIC) == 0)`，同样只看 STATIC 标志。
  - 2055：`outerParams = instance ? td.typarams : nil`。instance 为 true 时，外层的 `<T>` 会被拼进类型引用，也就是题面所说的"被错误地带上外围泛型"。
- `JavacHandlerUtil.java:2152`（`isRecord`）和 `:2168`（`isStaticAllowed`）。`isStaticAllowed` 已经把 record 视为可静态（`|| isRecord(typeNode)`），所以 `@Builder` 不会报"非静态嵌套类"错误。但 `namePlusTypeParamsToTypeReference` 没有同样处理。
- `src/core/lombok/javac/JavacNode.java:287` 的 `isStatic()`：只处理 INTERFACE、ENUM 以及父类型为接口或枚举的情况，不识别 record。
- `src/core/lombok/javac/handlers/HandleBuilder.java`：
  - 206 行 `job.isStatic = true`。
  - 238 行 `isStaticAllowed`。
  - 304 行：`buildMethodReturnType = namePlusTypeParamsToTypeReference(maker, parent, td.typarams)`，这是触发点，即 record 自身类型的引用。
  - 631、678、692、860 行：`namePlusTypeParamsToTypeReference(..., job.parentType, builderClassName, !job.isStatic, ...)`。这里用的是 job.isStatic，对类和 record 都是 true，所以 builder 自身引用基本没问题。
- `src/core/lombok/eclipse/handlers/EclipseHandlerUtil.java`：
  - 944 行 `MODIFIERS_INDICATING_STATIC = AccInterface | AccStatic | AccEnum`，不含 record。
  - 530-534、927、1005 行等处用它判断 instance。
  - 951-972 行 `fillOuterTypeParams`：955 行已有"enum 或 interface 内的类隐式 static"的特判，没有 record 的对应处理。

## 【3 并列与牵连】
- javac 与 Eclipse 是并列实现。Eclipse 的 `MODIFIERS_INDICATING_STATIC` 以及 `generateTypeReference`、`generateParameterizedTypeReference`、`fillOuterTypeParams` 有同样的盲点。隐藏测试大概率同时跑 javac 和 ecj。
- javac 内 `namePlusTypeParamsToTypeReference` 被 HandleBuilder、HandleSuperBuilder（`isStaticAllowed` 在 167 行，`job.isStatic=true` 在 137 行）、`HandleLockedUtil:163`、HandleWith、HandleConstructor 等调用。改这个工具方法会影响所有调用者。
- `JavacNode.isStatic()` 和 `isStaticAllowed` 是另一处"record 是否隐式 static"的判断，三处判断口径不统一。
- 同样的 bug 很可能也出现在 `@With`、`@SuperBuilder`、`@Jacksonized` 等对嵌套 record 生成引用的地方。
- 枚举、接口内部的类已有特殊处理，可作参照：`BuilderNestedInEnum`（issue #3014）。

## 【4 现有测试与约定】
- 测试在 `test/transform/resource/before/`，对应 `after-delombok/` 和 `after-ecj/` 目录。
- 相关用例：`BuilderSimpleOnRecord.java`（顶层泛型 record，`@Builder(access=PROTECTED)`）、`BuilderSingularOnRecord`、`SuperBuilderOnRecord`、`BuilderNestedInEnum`（注释写 "issue #3014"）。
- 现有用例都没有"泛型外层类 + 未写 static 的嵌套 record"。
- 我没有逐条核对这些用例的 after 文件内容，所以不引用具体断言。
- 约定：Java 规范规定嵌套 record 隐式 static，所以正确行为不是规范未定，而是明确的。
- 与题面不冲突：期望的是生成代码里不带外层类型参数。
- 新增测试的形式应是新的 before/after 文件，三份（before、after-delombok、after-ecj）。record 测试带 `// version 14:` 头。

## 【5 边界与隐含要求】
- 多层嵌套：`Outer<T>` 里套 `Mid`（非 static 内部类），里面再套 record。引用链到 record 为止就应该停止补类型参数，但上层仍可能需要保留。
- record 本身带泛型：`record R<U>(U u)`，自身的 `<U>` 必须保留，只去掉外层的 `<T>`。
- 外层是 record、接口、枚举的情形。
- builder 内部类、`toBuilder`、`@Singular`、`@Builder.Default`、`@Jacksonized`、`@SuperBuilder` 路径是否也生成了错误引用。
- Eclipse 编译器路径同样要修，否则 ecj 测试不过。
- delombok 的输出格式会变：生成的 `NestedRecord` 引用不应带 `Reproducer<T>.` 前缀。具体形式我没有验证。

## 【6 改动规模】
- 约 2 个核心文件（javac 和 Eclipse 各一个 HandleUtil），4-6 处局部判断，可能再加 `JavacNode.isStatic` 一处。
- 另外要新增 3 个测试资源文件。
- 属于局部修补，不需要新增结构。

## 【7 难点一句话】
难点不在改动量，而在于找全"隐式 static"的判断点：javac 与 Eclipse 两套代码里，判断静态的位置分散且口径不一（STATIC 标志、`isStatic()`、`isStaticAllowed`、`MODIFIERS_INDICATING_STATIC`、`fillOuterTypeParams`），漏掉任何一处，某个编译器或某个注解路径上仍会出错。