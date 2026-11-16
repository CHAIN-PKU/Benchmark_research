**档案：Coral v4 OpenAPI 导入把省略 `required` 的 path 参数当成可选**

【1 题面要点】
- 要求的行为：OpenAPI 导入 path 参数时一律视为 required，即使没写 `required`。非 path 参数的显式行为保持不变。要补有针对性的 importer 和 projection 测试。
- 题面没给复现，也没给期望输出，更没给修法建议。
- 关键句：
  - "Import path parameters as required regardless of an omitted `required` field, preserve explicit behavior for non-path parameters, and add focused importer/projection coverage."
  - "This can misclassify required path inputs as optional SQL filters."
- 题面还说"No new interfaces"。

【2 相关代码】
- 根因在 `crates/coral-spec/src/v4/surfaces/openapi/operations.rs:158-161`。`import_parameters`（第 85 行）里的 `required: parameter_obj.get("required").and_then(Value::as_bool).unwrap_or(false)` 在省略时默认为 false。
- 同一函数里，`location` 在第 148-151 行已解析，可以直接用 `location == Path` 判断。
- `parse_parameter_location`（第 261 行）负责把 "path" 映射成 `OpenApiParameterLocation::Path`。
- 下游 `crates/coral-spec/src/v4/projections/derive.rs`：
  - 第 67-73 行：Singleton 输出且存在 required 输入时，才把 projection 变成 `TableFunction`（Table 类）；否则是普通 Table，输入作为 Filter。因此改动会改变 projection 的种类。
  - 第 109 行：`required: input.required && input.default_value.is_none()`。
  - 第 89-103 行：Internal 暴露且 required 的输入会让 projection 变 Hidden 并产生诊断。
  - 第 145-162 行：`projection_input_sql_exposure`，Path 和 Query 都使用默认暴露。
- `projections/runtime.rs:108-117`：把 path 模板替换成 `{{filter.x}}` 或 `{{arg.x}}`。

【3 并列与牵连】
- 并列实现：`schemas.rs:172` 的 `required.contains(name)` 针对的是 schema 属性，与参数无关，不用改。
- request body 的 required（`operations.rs:237`）也不用改。
- 只有一个调用点，即 `import_parameters` 里的 `IrOperationInput` 构造。
- path 参数现在会变成 required，下游有三处连带影响：
  - 省略 required 的 path 参数，可能让 Singleton 操作从 Table 变成 TableFunction。
  - `required` 字段的取值变了，guide 文案可能随之变化（`projection_guide`）。
  - 带 default 的 path 参数在 `derive.rs:109` 仍会变成非 required。这是既有行为，可能需要确认。
- 在 `crates/coral-spec` 下没发现其他会省略 required 的 path 参数 fixture：`test_support.rs` 和各 tests 里的 path 参数都显式写了 `required: true`。我只查了 `in: path` 的 YAML 写法，没覆盖 JSON 形式的 fixture。`crates/coral-app/src/sources/manager.rs` 里有 4 处匹配 `in: path`，我没去看。

【4 现有测试与约定】
- `crates/coral-spec/src/v4/openapi_tests.rs` 里的 path 参数都显式写 `required: true`，例如第 77、142、201、283、343-344 行。
- 第 567 行 `importer_preserves_non_string_parameter_defaults` 只测 query 的 default（`per_page`、`archived`），断言的是 `default_value`（第 614-615 行）。这个测试没有断言 required。
- `projection_tests.rs` 的 path 参数同样显式 `required: true`（第 191-236 行）。
- 现有测试没有断言"省略 required"的行为，所以与题面期望不冲突。
- 外部规范是 OpenAPI：path 参数必须 `required: true`，没有仓库内的参考实现。
- 新测试放在这两个测试文件里：
  - importer 测试：省略 required 的 path 参数，断言 `input.required == true`；同时断言 query 参数省略时仍为 false，显式 `required: true` 的 query 仍为 true。
  - projection 测试：断言 `ProjectionInput.required`，以及 projection 的种类、暴露方式。

【5 边界与隐含要求】
- 显式 `required: false` 的 path 参数：规范上不合法。题面说"regardless of an omitted `required` field"，保险做法是 path 一律 true。如果测试预期显式 false 被保留，这里会出现分歧，需要判断。
- `$ref` 解析出来的参数和 path-item 级与 operation 级的合并（`merged`，第 92-141 行）：required 的计算在合并之后，所以合并后的结果自然适用。
- 带 default 的 path 参数：`derive.rs:109` 会把它的 required 置为 false。
- 非 path 参数（query、header、cookie）保持 `unwrap_or(false)`。
- 路径模板里出现、但没声明为参数的占位符不在本题范围内。

【6 改动规模】
- 核心改动是 `operations.rs` 一个文件、一处，约 3-5 行，是局部修补。
- 补测试涉及 `openapi_tests.rs` 和 `projection_tests.rs` 两个文件，各新增一个测试。
- 不需要新增结构，也不贯穿多层。

【7 难点一句话】
- 修复本身很小。难点在于：隐藏测试可能同时断言 projection 层的连带变化（Table 变 TableFunction、Filter 变 FunctionArg、guide 文案），需要确认改动后这些行为自洽，并判断显式 `required: false` 的 path 参数该保留还是覆盖。