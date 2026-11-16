# 仓库档案：LSP 对接口类型 `.` 补全为空

（查证了约 12 次，来源是 `completion.rs`、`lib.rs`、`store.rs`、`methods.rs`、`definition.rs`、`tests/lsp.rs`。我没有编译或运行代码。）

## 【1 题面要点】
- 期望行为：对接口类型的值输入 `ex.` 时，LSP 应补全该接口的方法。接口来源包括用户自定义和 stdlib/prelude。
- 复现：题面给了一段代码，参数 `ex: Example` 后接 `ex.`。Example 有 `fn example(self, name: string) -> string`。
- 没有给期望输出，也没有给修法建议。
- 题面末尾写着 "No new interfaces are introduced."，意思是不新增公共 API。
- 版本是 0.2.11，VSCode 和 Zed 都能复现。

## 【2 相关代码】
- `crates/lsp/src/completion.rs:192-237` 的 `get_instance_completions(type_id, snapshot, same_module)`：
  - 先补全 Struct 字段。
  - 再遍历 `snapshot.definitions()`，取前缀为 `{type_id}.` 的 `DefinitionBody::Value`。
  - 过滤条件是 `is_instance_method(definition.ty(), type_id)`（第 224 行）。
- `completion.rs:291-301` 的 `is_instance_method`：只有第一个参数的 `type_name` 等于 `type_id` 才算实例方法。
- 接口方法在注册时已经去掉了 `self`。依据是 `crates/semantics/src/checker/registration/methods.rs:321-347` 的 "Strip bare `self` parameter from the interface method type"。
- 所以接口方法的类型里没有接收者参数，`is_instance_method` 恒为 false，结果被过滤成空。这是最可能的根因。
- 同一个函数里，`get_type_completions`（第 275 行）的条件是 `!is_instance_method`。接口方法没有 self，会被它当成类型级（静态）方法。
- `crates/lsp/src/lib.rs:1119-1175` 是补全入口，有三条路径调用 `get_instance_completions`：
  - `detect_dot_context` 的 `Instance` 分支（第 1124 行）。
  - `self.` 分支（第 1139 行）。
  - `resolve_variable_type` 分支（第 1172 行）。
- `completion.rs:140-190` 的 `detect_dot_context` 通过 `type_name(&ty)`（`analysis.rs:20`）把 Nominal 类型转成 id。接口类型 `Example` 应能得到 `module.Example`，id 这一步大概没问题。
- 接口定义本体是 `DefinitionBody::Interface { definition: Interface }`，见 `crates/syntax/src/program/definition.rs:44,149`。
  - `Interface` 含 `generics`、`parents: Vec<Type>`、`methods: HashMap<EcoString, Type>`。
  - 方法类型已去 self，并且已经是 Forall 去壳后的 Function 类型。

## 【3 并列与牵连】
- 并列实现：`get_instance_completions` 和 `get_type_completions` 是成对的，都依赖 `is_instance_method`。改判定逻辑时两边要同步。否则接口方法会在 `Example.` 的类型级补全里出现（这不合理），或者两边都不出现。
- 父接口（嵌入接口）：`Interface.parents` 的方法也应该出现在补全里。
  - 参考实现是 `crates/semantics/src/store.rs:346-379` 的 `Store::get_all_methods`。它对 `interface.methods` 做泛型代入，再递归 `parents`。
  - LSP 的 `snapshot` 是否暴露 store，需要确认。我只看到 `snapshot.definitions()` 和 `snapshot.facts()`。
- 注册时还会为每个接口方法插入 `{module}.{Iface}.{method}` 的 Value 定义（`methods.rs:405` 以后）。所以按前缀遍历 definitions 能找到本接口自己的方法，但找不到父接口的方法。
- 泛型接口 `Iface<T>`：方法类型里带有 T，补全的 detail 显示的是未代入的类型。
- stdlib 接口，比如 `prelude.d.lis:581` 的 `error`、`database/sql.d.lis` 的 `Scanner`，都走同一条 definitions 路径，所以不需要单独处理。题面里的 "stdlib" 大概只是一个需要覆盖的用例。
- 可见性：接口方法继承接口的可见性。`same_module || visibility().is_public()` 在 pub 接口上应通过。

## 【4 现有测试与约定】
- 补全测试都在 `tests/lsp.rs`，形式是 `TestClient` 加 `client.completion(TEST_URI, line, col)`，再用 `completion_labels` 断言。例如：
  - 第 726-755 行 `completion_dot_on_local_variable`，断言 `labels.iter().any(|l| l == "dist")`，有 `"dist" method` 的提示信息，还断言了 `"x"` 字段。
  - 另外有 `completion_dot_on_for_loop_variable`（758）、`completion_dot_on_slice_variable`（828）、`stress_completion_on_self_in_impl`（3741）、`stress_cross_module_completion_on_struct_methods`（5829）。
- 没有任何补全测试覆盖接口。`tests/lsp.rs` 里提到 interface 的位置（1987、2008、2975 等）都是类型检查或 stress 用例，不是补全。
- 约定：补全 kind 是 `METHOD`、detail 是 `definition.ty().to_string()`。`definition_to_completion_kind` 已经支持 `Interface => INTERFACE`。
- 和题面不冲突。隐藏测试大概率是新增一个 `completion_dot_on_interface...` 之类的用例，断言 `"example"` 出现在 labels 里。
- 要注意：参数 `ex: Example` 的解析路径是 `resolve_variable_type` 里的 `Expression::Function` 分支，或者 `detect_dot_context` 的 `expression.get_type()`。`ex.` 后面没有成员，函数体里表达式不完整，解析是否成功需要在 parse 容错下确认。

## 【5 边界与隐含要求】
- 父接口（嵌入）的方法要包含进来，可能还要递归，要防止菱形继承造成的重复项（按 label 去重）。
- 泛型接口的类型参数代入。
- 带引用的接口值，如 `Ref<Example>`：`type_name` 已经剥 Ref。
- 约束 `T: Example` 时，对泛型值 `x: T` 的 `x.` 补全，走的是 `trait_bounds`（`store.rs:381`）。题面没提，但同属"对接口类型补全"。
- 接口里没有 self 的方法（静态签名）。这在 `methods.rs` 里 `has_self_receiver` 为 false 时保留原样，不应作为实例方法补全。
- 跨模块、非 pub 接口的可见性过滤。
- 接口类型的变量被推断为其他类型时，`resolve_variable_type` 里的 `remove_vars` 对 Nominal 接口应该没问题。
- 接口值上不应补出 struct 字段，且不能误伤现有 struct 方法过滤逻辑。

## 【6 改动规模】
- 预计只改 1 个文件 `crates/lsp/src/completion.rs`，在 `get_instance_completions` 里新增一个接口分支，约 15-40 行。
- 可能要读 `snapshot` 暴露的 definitions 以递归 `parents`。如果 `AnalysisSnapshot` 没有暴露 store 的方法，可能要在 `snapshot.rs` 加一个小访问器。
- 另需加测试。
- 属于局部修补，不跨层。

## 【7 难点一句话】
难在认清根因：接口方法类型在注册时被去掉了 `self`，导致 `is_instance_method` 恒为 false。次一级的难点是同时处理父接口递归与泛型代入，并避免 `get_type_completions` 里出现副作用。