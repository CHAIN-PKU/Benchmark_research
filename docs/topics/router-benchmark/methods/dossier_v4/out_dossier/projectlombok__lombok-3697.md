**档案：lombok SuperBuilder 泛型实参为数组时编译失败**

**【1 题面要点】**
- 要求的行为：`@SuperBuilder` 的子类继承带泛型的父类，且泛型实参是数组（如 `Integer[]`、任意数组）时，也要能正常编译，和非数组实参一样。
- 复现：父类 `@SuperBuilder public abstract class AbstractGenericsClass<S extends Serializable> { }`，子类 `@SuperBuilder public class GenericsClass extends AbstractGenericsClass<Integer[]> { }`。
- 报错：`GenericsClass.java:[8,1] wrong number of type arguments; required 3`。
- 期望：`The code should compile like with non-array-type generics.`
- 题面没有给修法建议，也没有给期望的生成代码。版本是 Lombok 1.18.32、javac 17。

**【2 相关代码】**（路径相对仓库根）
- `src/core/lombok/javac/handlers/HandleSuperBuilder.java:1100-1116` 的 `getTypeParamExpressions(typeParams, maker, source)`：
  - 它把类型参数或父类实参列表转成表达式列表，按节点类型逐个分支处理：`JCTypeParameter`、`JCIdent`、`JCFieldAccess`、`JCTypeApply`、`JCAnnotatedType`。
  - 没有 `JCArrayTypeTree` 分支，也没有 `JCWildcard` 或 `JCPrimitiveTypeTree` 分支，也没有 else。遇到这些节点会被静默丢弃。
  - 这与报错吻合：`Integer[]` 被丢掉，生成的 `AbstractGenericsClassBuilder<C, B>` 少了一个实参，期望 3 个（`S` + C + B）。
- `HandleSuperBuilder.java:254-259`：把 `extendsClause` 的 `JCTypeApply` 拆开，实参存入 `superclassTypeParams`。
- `HandleSuperBuilder.java:479`：`getTypeParamExpressions(superclassTypeParams, ...)` 用来生成抽象 builder 的 extends 子句，是出错点。
- `JavacHandlerUtil.java:2212-2275` 的 `cloneType` / `cloneType0`：已支持 `JCArrayTypeTree`（2234）、通配符、基本类型、注解类型。

**【3 并列与牵连】**
- `getTypeParamExpressions` 的调用点有 6 个：240、469、479、507、570、731。
  - 其中 240、469、507、570、731 传入的是 `job.typeParams`（`JCTypeParameter`，只会是 Ident）。
  - 只有 479 传入父类实参，所以数组、通配符、基本类型的问题只在这里出现。
- 通配符作为父类实参（如 `Parent<?>`）、`Parent<List<?>>` 同样可能落入被丢弃的分支。这是同一类 bug。
- Eclipse 实现 `src/core/lombok/eclipse/handlers/HandleSuperBuilder.java:291/308`：用 `getTypeParametersFrom(extendsClause)` 和 `mergeTypeReferences` 直接处理 `TypeReference`，不经过上面的分支函数，很可能本来就支持数组。但 ecj 下是否正常没有验证。
- 其他 `cloneType` 调用点（HandleBuilder 等）不受影响，除非修改 `cloneType` 本身。

**【4 现有测试与约定】**
- 测试是 `test/transform/resource/{before,after-delombok,after-ecj}` 三份资源的文件对比，没有断言语句。
- 现有相关用例：`SuperBuilderWithGenerics.java`、`SuperBuilderWithGenerics2.java`、`SuperBuilderWithGenerics3.java`（`extends Parent<Child.SomeInnerStaticClass>`）、`SuperBuilderNestedGenericTypes.java`、`SuperBuilderWithGenericsAndToBuilder.java`。
- 没有数组实参的用例。隐藏测试很可能是新增一个 `SuperBuilderWithGenericsArray` 之类的 before 与 after-delombok（也可能有 after-ecj）资源。
- 期望输出应是 `extends AbstractGenericsClass.AbstractGenericsClassBuilder<Integer[], C, B>`。
- 约定：用 `cloneType` 复制类型树。与题面无冲突。
- 我没有读 after 文件，也没有核对 delombok 的打印格式。

**【5 边界与隐含要求】**
- 多维数组 `Integer[][]`。
- 基本类型数组 `int[]`：`cloneType0` 已处理 `JCPrimitiveTypeTree`。
- 数组元素是泛型类型（`List<String>[]`）、限定名（`java.lang.Integer[]`）、带注解的数组类型。
- 通配符等其他此前被丢弃的节点。
- 之后也许还要确认 `$fillValuesFrom` 等方法的签名没有问题。这些方法用的是 `job.typeParams`，不涉及父类实参。
- 需要确认 ecj 侧是否同样通过。

**【6 改动规模】**
- 核心改动：`javac/handlers/HandleSuperBuilder.java` 的 `getTypeParamExpressions` 加一个分支，或改成统一走 `cloneType`，约 1 个文件、1-3 行。
- 另需新增测试资源 2-3 个文件。
- 属于局部修补，不需要新增结构。

**【7 难点一句话】**
- 定位并不难（分支函数漏掉 `JCArrayTypeTree`），难点在于是否只补数组还是一并覆盖其他被丢弃的节点，以及是否需要核对 ecj 侧。整体偏简单。