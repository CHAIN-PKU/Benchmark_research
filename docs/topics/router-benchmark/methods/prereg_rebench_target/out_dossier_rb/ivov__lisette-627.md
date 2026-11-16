# 仓库档案：`Unknown` 常量与内置 `Unknown` 类型冲突

我读过的代码有 `convert.rs`、`checker/mod.rs`、`builtins.rs`、`go_type.rs`、`types.rs` 和 `predeclared_shadowing.rs`，并对 `Unknown` 做了全仓搜索。**本次没有读 binding 生成器的源码，也没有读测试里对 Go 绑定的现有断言**，所以第 3、4 点里相关部分是推断，下面会标出。

## 【1 题面要点】
- 要求的行为：Go 依赖包里有名为 `Unknown` 的常量（discordgo 的 `Unknown` Locale）时，生成的绑定里出现在类型位置的 `Unknown` 必须仍然解析为 Lisette 内置的 `Unknown` 类型。
- 当前现象：编译时报 `resolve.value_in_type_position`，位置在 `go:github.com_bwmarrin_discordgo.d.lis` 的 4693、4695、4697 行。
  - `pub var Logger: fn(int, int, string, VarArgs<Unknown>) -> ()`
  - `pub var Marshal: fn(Unknown) -> Result<Slice<byte>, error>`
  - `pub var Unmarshal: fn(Slice<byte>, Unknown) -> Result<(), error>`
- 题面原话：「Lisette's built-in Unknown type should take precedence in type positions, or the binding generator should qualify/disambiguate imported names that shadow built-in types.」
- 复现：`import "go:github.com/bwmarrin/discordgo"`，调用 `discordgo.New(...)`，再 `lis run`。没有给期望输出，也没有给具体修法，只给了两个可选方向。
- 题面写明「No new interfaces」，所以不会新增公开 API。

## 【2 相关代码】
- `crates/semantics/src/checker/registration/convert.rs:58-111`：`convert_to_type` 里的 `Annotation::Constructor` 分支。
  - 第 83 行调用 `resolve_type_with_arity`。
  - 第 101 行 `classify_non_type_name` 发现解析结果是 `DefinitionBody::Value`，于是在第 104 行报 `value_in_type_position`。**这是报错的直接来源。**
- `convert.rs:292-317`：`resolve_type_with_arity`。
  - 先走 `resolve_type_name`，只有在"元数相符"这个附加条件下才回退到 prelude。
  - 当前模块里的 `Unknown` 常量优先命中。回退到 prelude 的条件是元数不同，而这里元数都是 0，所以不会触发。
- `crates/semantics/src/checker/mod.rs:325-359`：`lookup_qualified_name`。
  - 先看带前缀的导入。
  - 再看当前模块自身的 definitions，这里 `go:...discordgo.Unknown` 作为 Value 被找到。
  - 最后看 unprefixed imports。
  - **没有 prelude 回退，也不区分 Type 和 Value。**
- `checker/mod.rs:489-502`：`resolve_type_name`。它调用 `lookup_qualified_name`，再用 `store.get_type(&qualified_name)` 取类型。
- `checker/mod.rs:504-512`：`resolve_type_from_prelude`，拼出 `prelude.{name}`。
- `crates/semantics/src/checker/registration/builtins.rs:14-33, 67-69`：`type_unknown` 通过 `builtin_type` 和 `builtin_qualified_name` 走 `lookup_qualified_name("Unknown")`。
  - 在 discordgo 模块上下文里同样可能命中常量。这是同一个问题的第二个入口，我推断它有风险，未验证。
- `crates/semantics/src/checker/registration/convert.rs:235-290`：`classify_non_type_name`，负责生成报错的分类和 help 文案。

## 【3 并列与牵连】
- **并列的解析入口有三处**，都按"当前模块优先"的规则找名字：
  - `convert_to_type` 的 Constructor 分支。
  - `type_unknown` / `builtin_type`。
  - `crates/semantics/src/passes/checks/generics.rs:196` 里另一份同名的 `lookup_qualified_name` 副本，它只看当前模块。
- emit 层：`crates/emit/src/types/go_type.rs:275-293` 的 `unqualify_name` 把 `Unknown` 和 `X.Unknown` 一律输出为 `any`。
  - 如果让某个 Go 包里的名字真的叫 `Unknown`，这里会把它当内置类型处理。
  - 反过来，这里按名字字符串判断，不区分是常量还是类型，所以不需要为这个 issue 改。
- `crates/syntax/src/types.rs:872`：`is_unknown` 用 `has_name("Unknown")` 判断，也是按名字匹配。
- `crates/cli/src/handlers/doc.rs:726, 927` 把 `Unknown` 当预定义类型名列出。
- `crates/semantics/src/passes/checks/predeclared_shadowing.rs:58-60` 只保留了 `any` 和 `comparable`。
  - 它禁止的是用户自己声明的类型和泛型参数与这两个名字相同，**不涵盖 `Unknown`，也不检查 Go 绑定里的名字。**
- 这个问题可能不止 `Unknown`。其他内置名（例如 `Unit`、`Never`、`VarArgs`、`error`）如果 Go 包里有同名常量或函数，也会出同样的错。这是推断，未验证。

## 【4 现有测试与约定】
- `tests/ui/errors/snapshots/infer_not_a_type_*.snap` 里有五个 `value_in_type_position` 快照（`unit_variant_local`、`unit_variant_prelude`、`constructor_variant`、`function_name`、`function_returning_enum`）。
  - 它们断言的是**用户写代码**把值当类型用时要报错，这个行为必须保留。
  - 修复只应影响内置类型名遇到同名 Value 的情况，不应放宽这类报错。
- `tests/spec/infer/types.rs:2312` 只有一个字符串字面量 `"Unknown"`，不是相关断言。
- `tests/spec/emit/types.rs` 里有 10 处提到 `Unknown`，应该是 `Unknown` → `any` 的 emit 断言，我没有细读。
- 隐藏测试很可能是 spec 或 ui 测试，用一个带同名常量的 Go 绑定或本地模块去验证。**这是推断，我没有看到测试夹具的样子。**
- 约定：Go 绑定的 `.d.lis` 文本里直接写裸 `Unknown`（题面报错片段可证），所以"让绑定生成器改写成限定名"需要知道 prelude 的限定写法。
  - 我没有查证 Lisette 是否支持在类型位置写 `prelude.Unknown`，这一点未知。
- 与题面不冲突：题面要求的"内置类型优先"和现有的值/类型区分规则相容。

## 【5 边界与隐含要求】
- 只在"当前模块里同名的是 Value，而 prelude 里有同名 Type"时回退到 prelude。如果当前模块里有同名**类型**（用户自己的 `Unknown` struct），应该仍然优先用户类型。
- 带参数的内置类型（`VarArgs<Unknown>`）里的内层 `Unknown` 要同样处理，因为 `convert_to_type` 对 params 是递归调用的。
- `Unknown` 作为函数参数、返回值、`Result` 的类型参数、`pub var` 的类型，这些位置要全部覆盖。
- 常量本身在值位置仍然能被引用，例如 `discordgo.Unknown` 作为值使用不能被破坏。
- `type_unknown`（`builtin_type`）在 discordgo 模块上下文里不能误解析成常量。
- 别的 Go 包里有同名常量遮蔽 `Unit`、`Never` 等内置名时，最好一并覆盖。
- 缓存：`self.builtins` 按名字缓存，要注意缓存里存的是 prelude 的版本。
- LSP 的补全、悬停和跳转定义里也有 `Unknown`，行为不应变化。

## 【6 改动规模】
- 最小修法：只改 `crates/semantics/src/checker/registration/convert.rs`，局部修补，约 1 个文件、1 到 2 处。
- 需要一起改的可能有 `checker/mod.rs` 的 `lookup_qualified_name` 或 `builtin_qualified_name`，约 1 个文件、1 处。
- 再加 1 到 2 个测试。
- 不需要新增结构。
- 如果选"绑定生成器限定名字"的方向，会涉及 `crates/cli/src/typedef_regen.rs` 和 `crates/deps` 一带的生成逻辑，**我没有读过，规模未知**，也要重新生成已有绑定，所以倾向于前一种。

## 【7 难点一句话】
代码定位很容易（报错点和解析顺序都很清楚），难在判断**回退规则放在哪一层、放多宽**：既要让内置类型名在遇到同名 Value 时回退到 prelude，又不能破坏现有五个 `value_in_type_position` 报错，也不能误伤用户自己声明的同名类型。