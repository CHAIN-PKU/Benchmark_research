# 仓库档案：ty 类型别名 variance 推断丢失

我没有运行代码，也没有跑 mdtest。第 5 节和第 7 节里有几处是推断，已标注。

## 【1 题面要点】
- **要求的行为**：`type RefBox[T] = Box[T]` 里 T 是 invariant，`type RefRefBox[T] = RefBox[T]` 里 T 应当仍是 invariant，现在却变成 bivariant。
- **复现**：有，是 playground 链接加一段 dataclass 示例。
- **期望输出**：只有注释里的 "T is invariant"，没有诊断输出。
- **修法建议**：issue 正文没有，但 Evaluation contract 说了：
  - "Variance inference for both PEP 695 and legacy generic type aliases must recurse through the alias value rather than treating every alias as bivariant."
  - "Preserve covariant, contravariant, invariant, and bivariant results through multi-level and reordered multi-parameter alias chains."
  - "Recursive or mutually recursive alias cycles must terminate safely using the existing bivariant cycle fallback."
- **接口**：不新增接口。

## 【2 相关代码】
- **根因**：`crates/ty_python_semantic/src/types.rs:6870` 的 `impl VarianceInferable for Type`。`Type::TypeAlias(_)` 与 `Dynamic`、`Never` 等一起落在 `=> TypeVarVariance::Bivariant` 这个兜底分支里。
  - `RefRefBox` 的 RHS 是 `Type::TypeAlias(RefBox[T])`，所以得到 Bivariant。
  - 单层别名的 RHS 是 `Box[T]`，是类的泛型实例，所以单层没问题。
- **已有的别名路径**：`known_instance.rs:201-210` 里 `KnownInstanceType::TypeAliasType` 用 `type_alias.raw_value_type(db).variance_of(...)`。
  - 它用的是未特化的原始 RHS，不是 `value_type`。
  - 它没有 salsa cycle 保护。
  - 它只处理 `KnownInstance` 形态，不处理 `Type::TypeAlias`。
- **别名定义**：`type_alias.rs`
  - `PEP695TypeAliasType` 在第 24 行，字段有 `rhs_scope` 和 `specialization: Option<Specialization>`。
  - `raw_value_type` 在第 66 行，自带 `cycle_initial = Type::divergent`。
  - `value_type` 在第 53 行，会应用特化。
  - `generic_context` 在第 131 行。
  - `TypeAliasType` 枚举在第 204 行，`value_type` 在第 244 行，`raw_value_type` 在第 251 行。
- **同类的 variance 实现**：
  - `class/static_literal.rs:2860` 和 `function.rs:1293` 都用 `#[salsa::tracked(cycle_initial=|..| Bivariant)]`。
  - `function.rs:1292` 的注释写着 "Class and generic-alias variance use the same `Bivariant` cycle fallback."，也就是仓库已有这个约定。
- **trait 与工具**：`variance.rs:135` 的 `VarianceInferable` 和 `with_polarity`，以及 `compose` 和 `join`。

## 【3 并列与牵连】
- **两条路径要同步**：`Type::TypeAlias`（`types.rs:6870`）和 `KnownInstanceType::TypeAliasType`（`known_instance.rs:204`）。更干净的做法是在 `TypeAliasType` 上加一个共用的 tracked `variance_of`，两处都调用它。
- **manual 别名**：`ManualPEP695TypeAliasType`（`type_alias.rs:154`）没有 generic_context，也没有 specialization，但它的 `value_type` 本身有 cycle 保护。
- **legacy 别名**：
  - 我没有找到专门的 legacy 别名类型。`known_instance.rs` 里 `GenericAlias` 只有 `type[...]` 和 `Callable`，`type_alias.rs:266` 注释写着 "TODO: Add support for generic non-PEP695 type aliases"。
  - 所以 `Alias = Box[T]` 这类旧式别名很可能直接是 `Type::GenericAlias`（类的特化），已有 `types.rs:6808` 处理。这是推断，需要实测确认。
  - 题面要求 "both PEP 695 and legacy"，可能只是要求补测试，也可能还有未覆盖的路径。
- **牵连**：别名嵌在 union、intersection、`Callable` 签名、类的属性和方法里时都会走到这个分支。修好后这些位置的 variance 结果可能变化，已有的 mdtest 快照也可能变。

## 【4 现有测试与约定】
- **Rust 单测**：`types/tests.rs:327-336` 定义了别名，`:340-401` 断言：
  - `CovariantAlias` 是 `Covariant`，`ContravariantAlias` 是 `Contravariant`，`InvariantAlias` 是 `Invariant`，`BivariantAlias` 是 `Bivariant`。
  - `ParamSpec` 的几个用例也有断言。
  - `RecursiveAlias[T] = None | list[RecursiveAlias[T]]` 断言为 `Bivariant`（`:389-394`）。
  - `RecursiveAlias2[T] = None | list[T] | list[RecursiveAlias2[T]]` 断言为 `Invariant`（`:396-401`）。
  - 这些断言都是通过 `KnownInstanceType::TypeAliasType(..).variance_of` 调用的。
  - 递归那两条里的内层 `RecursiveAlias[T]` 是 `Type::TypeAlias`，目前靠兜底的 Bivariant 才成立。修复后必须靠 cycle fallback 保持这两个结果。
- **mdtest**：`resources/mdtest/generics/pep695/variance.md:942-999` 的 "Type aliases" 一节，写着 "The variance of the type alias matches the variance of the value type (RHS type)."
  - 它只测了一层别名，用 `is_subtype_of(MyCovariant[Literal[1]], MyCovariant[int])` 之类的断言。
  - 没有多层别名，也没有多参数重排的用例。
- **环检测约定**：`variance.md:443-462` 说明环里先假设 bivariant，再迭代到不动点。
- **外部规范**：typing spec 的 variance 一节。
- **与题面冲突**：只有对内层别名的 Bivariant 兜底，与题面冲突。其余不冲突。

## 【5 边界与隐含要求】
- **应用特化**：内层别名带 specialization，例如 `type B[T, U] = A[U, T]`。要得到正确的变体，必须对特化后的 RHS 取 variance，或者把参数映射到别名自己的参数上。
  - 直接用 `raw_value_type` 会丢掉 T 和 U 的映射，在重排参数时会得到错误结果。
  - 题面的 "reordered multi-parameter alias chains" 正指向这里。
- **typevar 归属**：`typevar` 是外层别名的 `BoundTypeVarInstance`，而内层 RHS 里展开后出现的是外层的 T。需要确认 `value_type` 的特化结果里引用的是否就是外层 typevar（我倾向于是，这是推断，需实测）。
- **非泛型别名**：`value_type` 里没有该 typevar 时应返回 Bivariant。
- **循环与互递归**：
  - 自递归和互递归别名要靠 salsa cycle_initial 终止。
  - `raw_value_type` 本身会返回 `Divergent`，那个分支在 `types.rs:6855` 已经是 Bivariant。
  - 需要确保对 `value_type` 的递归不会引起 cycle 不收敛（`ManualPEP695` 的注释提到过这个问题）。
- **组合极性**：别名出现在逆变位置（如 `Callable` 参数）时，要靠已有的 `with_polarity` 组合，别名自身不需要处理。
- **ParamSpec**：别名里有 ParamSpec 时的特化方向，见 `generics.rs:1632 specialization_variance` 里的 flip。
- **legacy 与 manual**：`TypeAliasType("X", Box[T], type_params=(T,))` 目前没有 generic_context，可能需要决定是否支持，也可能不在范围内。

## 【6 改动规模】
- **文件数**：核心是 1 到 3 个文件。
  - `types.rs`：把 `Type::TypeAlias(_)` 从兜底分支拆出来。
  - `type_alias.rs`：加 tracked 的 `variance_of`，带 Bivariant 的 cycle_initial。
  - `known_instance.rs`：改为复用它。
- **测试**：`types/tests.rs` 和 `variance.md` 各加用例，包括多层链、参数重排、四种 variance、自递归和互递归。
- **性质**：局部修补，不需要新增结构，也不贯穿多层。代码量大概几十行，加上测试。

## 【7 难点一句话】
改法本身很短，难点是别名在 salsa cycle 下的收敛：既要沿特化后的 RHS 递归，保持参数重排时的正确映射，又要让已有的递归别名测试（`RecursiveAlias` 为 Bivariant，`RecursiveAlias2` 为 Invariant）和互递归都稳定终止。legacy 别名那部分是否需要额外改动，我没有核实。