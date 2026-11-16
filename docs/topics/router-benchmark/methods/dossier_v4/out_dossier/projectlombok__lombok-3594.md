# 仓库档案：@SuperBuilder 与父类泛型实参带类型注解

我做了 7 次搜索和读取。没有跑代码，也没有查 Eclipse 一侧 `getTypeParametersFrom` 和 `copyType` 的实现，所以 Eclipse 部分是推断。

## 【1 题面要点】
- **要求的行为**：`@SuperBuilder class ChildWithAnnotation extends Parent<@ValidDouble Double>` 要能编译，行为与无注解的 `Child extends Parent<Double>` 一致。
- **复现**：有。给了 `Parent<T extends Comparable<T>>`、`@Target(TYPE_USE, ANNOTATION_TYPE)` 的 `@ValidDouble`，以及子类。还附了 GitHub 示例仓库。
- **报错**：`error: wrong number of type arguments; required 3`。
- **期望输出（来自 delombok 对比）**：
  - 正确的是 `extends Parent.ParentBuilder<Double, C, B>`。
  - 出错的是 `extends Parent.ParentBuilder<C, B>`，`Double` 被丢掉了。
- **修法建议**：题面没有。它只指出了症状，也就是超类的类型实参丢失。

## 【2 相关代码】
- `src/core/lombok/javac/handlers/HandleSuperBuilder.java:1100-1114` `getTypeParamExpressions(...)`
  - 这是根因的最大嫌疑。它把类型实参列表转成 `JCExpression`，只处理四种节点：`JCTypeParameter`、`JCIdent`、`JCFieldAccess`、`JCTypeApply`。
  - 带注解的类型是 `JCAnnotatedType`，不在这四种里。它会被静默跳过，不报错也不追加，所以 `Double` 被丢掉，只剩 C、B 两个实参。
- `HandleSuperBuilder.java:252-269` 提取 `extendsClause`
  - `superclassTypeParams = ((JCTypeApply) extendsClause).getTypeArguments()`（256 行）。
  - 这里是把原始的、可能带注解的实参列表保存下来的地方。
- `HandleSuperBuilder.java:455-489` `generateBuilderAbstractClass`
  - 第 479 行调用 `getTypeParamExpressions(superclassTypeParams, ...)`，用来构造 `extends` 子句。这是题面症状出现的位置。
- `src/core/lombok/eclipse/handlers/HandleSuperBuilder.java:274-315`
  - 用 `getTypeParametersFrom(extendsClause)` 和 `mergeTypeReferences` 构造超类 builder 的类型实参，对应 Eclipse 一侧。
- `src/core/lombok/javac/handlers/JavacHandlerUtil.java` 里现成的工具：
  - `JCAnnotatedTypeReflect`（1228 行起）。
  - `getTypeUseAnnotations`、`removeTypeUseAnnotations`（2024-2032 行）。
  - `cloneType0`（2252-2255 行）：对 `JCAnnotatedType` 已有克隆分支，会克隆注解并重建。

## 【3 并列与牵连】
- `getTypeParamExpressions` 共有 5 个调用点：HandleSuperBuilder 的 240、469、479、507、570、731 行（共 6 处）。
  - 其中只有 479 行传入的是超类实参，可能带注解。
  - 其余传入 `job.typeParams`，元素是 `JCTypeParameter`，不会受影响。
- 如果在函数内加 `JCAnnotatedType` 分支，所有调用点都会走到它，但只有 479 行实际触发。
- 注意"追加时克隆还是去掉注解"这个选择：
  - `extends` 子句里保留注解是合法的，克隆即可。
  - 去掉注解则更简单安全。
- 非 SuperBuilder 的 `@Builder` 不涉及超类 builder，不受影响。
- Eclipse 一侧要同样检查，因为 `mergeTypeReferences` 和 `copyType` 处理带注解的 `TypeReference` 时是否正常，我没有验证。Eclipse 的注解存放在 `TypeReference.annotations` 里，不是单独的节点类型，所以那边可能本来就没问题。

## 【4 现有测试与约定】
- 测试是 `test/transform/resource/before/` 与 `after-delombok/`、`after-ecj/` 三份对照文件的形式。
- 现有相关用例：`SuperBuilderWithGenerics*.java`（1、2、3）、`SuperBuilderNestedGenericTypes.java`、`SuperBuilderSingularAnnotatedTypes.java`（带 `@Target(ElementType.TYPE_USE)`，8 行）、`CheckerFrameworkSuperBuilder.java`。
- 我没有打开这些文件的断言内容，所以没有可引用的具体断言行。
- 没有现成的"超类实参带注解"用例。隐藏测试很可能是新增的一个 before/after 三件套。
- after-delombok 与 after-ecj 的具体输出格式（注解是保留还是去掉）会决定实现选择，隐藏测试可能对此有断言。这是最大的不确定点。
- 外部规范：JLS 允许 `extends` 子句的类型实参带 TYPE_USE 注解。与题面期望不冲突。

## 【5 边界与隐含要求】
- 多个实参，其中只有部分带注解。例如 `Parent<@A String, @B Integer>`。
- 注解带参数，例如 `@TA(x=5)`。
- 嵌套泛型里的注解，例如 `Parent<List<@A String>>`。`JCTypeApply` 分支用 `cloneType`，大概已处理。
- 通配符与数组类型实参。目前这些节点同样会被静默丢弃（例如 `JCWildcard`、`JCArrayTypeTree`），可能是同类遗漏。
- 全限定名加注解，例如 `Parent<java.lang.@A Double>`。
- `extendsClause` 自身带注解（`extends @A Parent<...>`）。
- 修复应保证生成的 `extends` 子句的实参个数等于超类类型参数个数加 2。
- 注意 Java 8 下 `JCAnnotatedType` 通过反射访问（`JCAnnotatedTypeReflect`），要用现成工具而不是直接引用该类。

## 【6 改动规模】
- 核心修复在 1 个文件 1 个函数，约几行：`getTypeParamExpressions` 增加分支。
- 另需新增测试资源：`before` 加 `after-delombok`，可能还有 `after-ecj`，共 2-3 个文件。
- Eclipse 一侧可能不需要改。
- 属于局部修补，不涉及新结构。

## 【7 难点一句话】
代码改动本身很小，难点在于定位：问题是静默丢弃，没有报错，要发现 `getTypeParamExpressions` 的 `instanceof` 链漏了 `JCAnnotatedType`。其次要选对"保留注解还是去掉"，以匹配隐藏测试的 after 文件。