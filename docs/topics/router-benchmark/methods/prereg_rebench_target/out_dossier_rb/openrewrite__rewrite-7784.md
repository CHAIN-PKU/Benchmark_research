# 仓库档案：RemoveUnusedImports 误删仅出现在泛型参数中的 import

我没有运行代码，所以根因只是静态阅读后的推断，没有复现确认。

## 【1 题面要点】
- 期望行为：`class BloomFilterRef<T> extends AtomicReference<BloomFilter<T>>` 中，`BloomFilter` 只出现在泛型实参里，其 import 必须保留。
- 题面给了复现源码、期望输出（两条 import 都在）和实际输出（`com.google.common.hash.BloomFilter` 被删）。
- 题面没有给修法建议，堆栈部分是空占位符，没有报错。
- 关键特征：
  - 类带自己的类型参数 `<T>`。
  - 泛型嵌套两层：`AtomicReference<BloomFilter<T>>`。
  - 出现位置是 `extends` 子句。
  - 测试里带有 `@SuppressWarnings` 注解。
- 题面没写测试是否把 guava 放进 classpath。

## 【2 相关代码】
- `rewrite-java/src/main/java/org/openrewrite/java/RemoveUnusedImports.java`
  - `RemoveUnusedImportsVisitor.visitCompilationUnit`（65–332）是全部判定逻辑。
  - 第 95–118 行：遍历 `cu.getTypesInUse().getTypesInUse()`，按包名归集成 `typesByPackage`。
    - `JavaType.Parameterized` 分支（96–109）：加入 raw type，再对每个 `typeParameter` 调 `TypeUtils.asFullyQualified` 后加入。
    - 这一分支**只展开一层**类型参数，没有递归。
    - 嵌套参数如果是 `Parameterized`，会以 Parameterized 本身入集合。
    - 类型参数若是 `GenericTypeVariable`、通配符、数组，`asFullyQualified` 返回 null，会被丢掉。
    - `FullyQualified` 分支（110–117）不处理 Parameterized。
  - 非静态 import 的判定在 215–277 行：
    - 第 227 行：`combinedTypes.isEmpty() && !unqualifiedTypeNames.contains(...)` 即判为未使用。
    - 第 264 行：`sourceIdentifierNames` 不含简单名即判为未使用。
    - 第 269–274 行：`combinedTypes` 里没有 FQN 相同的类型，且不在 `unqualifiedTypeNames` 里，也判为未使用。
  - `collectUnqualifiedTypeNames`（480–520）：只看 `identifier.getType() instanceof FullyQualified` 且 `getFieldType()==null` 的标识符。
    - 如果泛型实参里的 `BloomFilter` 标识符类型是 Parameterized，也属于 FullyQualified，理论上会被收集。
    - 它收集的名字用 `getFullyQualifiedName()`，Parameterized 返回的是 raw FQN。
  - `collectSourceIdentifierNames`（526–539）：收集全部标识符简单名。
- `rewrite-java/src/main/java/org/openrewrite/java/internal/TypesInUse.java`
  - `FindTypesInUse.visitType`（535–553）：把类型加入 `types`，但当前 cursor 值是 `J.ClassDeclaration` 或 `J.Lambda` 时跳过。
  - `visitIdentifier`（509–519）：父节点是 `J.ClassDeclaration` 的标识符直接跳过（"skip type of class"）。
  - 疑点：`extends`、`implements` 子句里的 TypeTree 如何走到 `visitType`。这是我没来得及验证的地方。

## 【3 并列与牵连】
- `TypesInUse` 同时被很多其他配方使用（`UsesType`、`FindTypes` 等），见 `TypesInUse.java` 的 trie 构建。改它的收集规则会牵连全部使用方；改 `RemoveUnusedImports` 只影响本配方。
- `getAmbiguousStaticImportNames`（334–358）和静态 import 分支（143–214）是并列路径，但与本题的非静态类型 import 无关。
- 同一个 `typesByPackage` 构建逻辑被非静态、静态、通配符三处消费（157、217–218、234–240）。如果改成递归展开类型参数，会同时影响：
  - 通配符展开时的 `combinedTypes.size()` 与 `classCountToUseStarImport` 阈值比较（234 行）；
  - `usedWildcardImports` 的判定。
- 我没有查 `ChangeType`、`AddImport`、`OrderImports` 里是否有类似的“只展开一层”逻辑。

## 【4 现有测试与约定】
- 测试文件：`rewrite-java-test/src/test/java/org/openrewrite/java/RemoveUnusedImportsTest.java`。
- 已有泛型相关用例：
  - 第 111、143 行：`MyMapEntry<K, V> implements Entry<K, V>`。
  - 第 1423、1502 行：`HashMap<Integer,String>`。
  - 第 1800–1801 行：`Pair<String, String> pair`、`Table<String> table`。
  - 这些都是单层泛型，或出现在字段、局部变量里，没有“类型参数 + extends + 嵌套泛型”的组合。
- 我没有逐条核对这些用例的具体断言，所以不能引用具体断言文本。
- 约定：这个配方受 `NoMissingTypes` 前置条件保护（59 行），类型缺失时整个文件不处理。
- 题面期望与现有行为没有冲突。正确行为就是“有引用就保留”。

## 【5 边界与隐含要求】
- 更深的嵌套，比如 `A<B<C<D>>>`。
- 通配符与上下界：`List<? extends Foo>`、`List<? super Foo>`。
  - 这类参数的类型是 `GenericTypeVariable`，`asFullyQualified` 对它返回 null。
- 类型参数的 bound：`class X<T extends Foo>`。
- 数组类型参数：`List<Foo[]>`。
- 内部类作为类型参数：`Map<Outer.Inner, X>`。
  - 第 103–107 行对内部类按外层类的 FQN 归包。
- 位置多样：`implements`、`throws`、方法返回类型、方法类型参数、`new Foo<Bar<Baz>>()`、强制转换、`instanceof`。
- 通配符 import（`com.google.common.hash.*`）下的同一情形。
  - 展开时 `unqualifiedTypeNames` 过滤（240 行）可能漏掉只出现在泛型里的类型。
- 保留要求：不能因此保留本来确实没用的 import，否则会破坏已有用例。

## 【6 改动规模】
- 预计只改 1 个主文件（`RemoveUnusedImports.java`），约 1–2 处，外加 1 个测试文件。
- 如果根因在 `TypesInUse.FindTypesInUse`，则是第二个文件，但那里影响面更大。
- 大概率是局部修补：递归展开 `Parameterized` 类型参数，或改为遍历 `J.ParameterizedType` 的标识符。
- 不需要新增结构。

## 【7 难点一句话】
难点是在没有运行环境的情况下找准根因：一层展开的逻辑看起来应该已经覆盖了 `BloomFilter<T>`，所以真正的漏洞可能在 `TypesInUse` 对 `extends` 子句泛型实参的收集，或在 `Parameterized` / `GenericTypeVariable` 的处理上。修的时候还要避免误伤已有的“确实未使用”用例。