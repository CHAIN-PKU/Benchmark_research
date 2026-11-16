# 仓库档案：SQL 同名表在不同 schema 下被判为重复定义

我这次读了定义登记表、SQL 变量访问器、边计算、各处调用点和 `test_dataflow_cases.py`。没有运行任何测试。

## 【1 题面要点】
- 要求的行为：两个 SQL cell 分别执行 `CREATE TABLE finance.datalake.xx` 和 `CREATE TABLE finance.information_layer.xx`，不应再报“redefines variables”。
- 题面没有给 diff 或修法。它给了复现 SQL，报错是 `'xx' was also defined by: dl`。"Expected Behavior" 一节正文为空，只写了“两条语句都应无冲突地执行”。
- 评估契约原话：
  - “Track SQL definitions by their complete qualified identity.”
  - “same fully qualified name, or the same unqualified name, still is [multiply defined]”。
  - “Preserve the user-facing table variable, defining-cell ownership, deletion behavior, and conflict reporting for genuine collisions.”
- 接口：`DefinitionRegistry.get_multiply_defined()` 的返回类型要从 `list[Name]` 改成 `list[tuple[Name, set[CellId_t]]]`。它要用“冲突感知分组”：同叶名、不同限定名不算冲突，限定名相同才算。

## 【2 相关代码】
- `marimo/_runtime/dataflow/definitions.py:39-74` `register_definition`：根因在这里。
  - 第 59-67 行只在 `typed_def not in typed_definitions`（种类不同）时才检查 `qualified_name`。
  - 同名同种类（table/table）会落入 `else`，无条件 `definitions[name].add(cell_id)`。
  - 所以 `xx` 的两个 cell 都进了 `definitions["xx"]`。
- `definitions.py:147-153` `get_multiply_defined`：现在只看 `len(definers) > 1`，需要改成按限定名分组，并返回元组。
- `definitions.py:76-100` `unregister_definitions`：按叶名清理，删除时的行为要和新结构保持一致。
- `marimo/_ast/visitor.py:734-751`：对表和视图调用 `_define(None, _table.table, VariableData("table", qualified_name=_table.qualified_name))`。
  - 变量名是叶名，限定名放在 `qualified_name` 里。
  - `defined_names` 里存的是限定名。
- `marimo/_ast/visitor.py:361-368`：`_define_in_block` 把每次定义追加进 `variable_data[name]` 列表。
- `marimo/_runtime/dataflow/graph.py:101-104` 注册定义，`graph.py:213` 删除定义，`graph.py:266-268` 转发 `get_multiply_defined`。
- `marimo/_runtime/dataflow/edges.py:166-217`：按叶名取 `definitions.definitions.get(name)` 作为父 cell，再用 `find_sql_hierarchical_matches` 和 `matches_hierarchical_ref` 做层级过滤。

## 【3 并列与牵连】
- **报错的实际来源不是 `get_multiply_defined`。** `marimo/_lint/validate_graph.py:55-65` 的 `check_for_multiple_definitions` 直接遍历 `graph.definitions[name]`，并用 `len(defining_cells) > 1` 判断，这才是用户看到的那条报错。
  - 如果只改 `get_multiply_defined`，题面里的报错不会消失，除非让 `definitions` 本身不再把两个 cell 合并，或者让 validate_graph 改用新方法。
- `get_multiply_defined` 的调用点都要适配新的元组返回值：
  - `marimo/_ast/app.py:612-617` 用 `multiply_defined_names[0]` 拼接错误信息。
  - `marimo/_code_mode/_context.py:1561` 和 `1592-1610`：`set(graph.get_multiply_defined())` 做集合差，随后 `sorted(new_multiply_defined)` 和 `graph.get_defining_cells(name)`。元组里含 `set`，不可哈希，这里会直接崩。
  - `marimo/_ai/_tools/tools/dependency_graph.py:191` 的 `sorted(graph.get_multiply_defined())` 和 `:254-263` 的字符串拼接。
  - `marimo/_convert/ipynb/to_ir.py:164-169` 遍历 `multiply_defined_names`。
  - `tests/_ai/tools/tools/test_dependency_graph.py:62` 把 mock 的返回值设为 `[...]`，`:263` 断言 `["x"]`。返回类型一变，这些 mock 和断言也要改。
- 其它直接读 `graph.definitions` 的地方（按叶名为键）：
  - `runtime.py:216`、`:1269`、`:1943-1947`。
  - `hooks_post_execution.py:299`。
  - `_save/hash.py` 的 450、769、946、998 行。
  - `cell_runner.py:579` 和 `597`，`strict.py:102`，`_runtime/dataflow/__init__.py:175`，`exceptions.py:37`。
  - 如果改变 `definitions` 的键结构，这些地方都会受影响。
- 删除路径：`unregister_definitions(cell_id, cell.defs)` 的 `cell.defs` 是叶名集合。同一个叶名对应多个限定名时，必须只清理该 cell 自己的那一份。

## 【4 现有测试与约定】
- `tests/_runtime/test_dataflow_cases.py:290-306` 的用例“different schemas with same table name”：
  - 代码是 `schema_one.my_table` 和 `schema_two.my_table` 两个 cell。
  - 断言 `expected_defs={"0": ["my_table"], "1": ["my_table"], "2": []}`。
  - 因此用户可见的 `defs` 仍然是叶名，两个 cell 都保留 `my_table`。题面“Preserve the user-facing table variable”与此一致。
  - 这个用例只测边和 defs，没有测多重定义，所以现在能通过，但它也说明限定名分开的意图已经存在。
- `tests/_runtime/test_dataflow_cases.py:491-505` 的用例：`CREATE TABLE my_table AS SELECT * FROM schema_one.my_table`，引用 `my_table` 的 cell 只依赖 cell 0。
- `tests/_lint/test_validate_graph.py:26-55` 的断言形如 `MultipleDefinitionError(name="x", cells=("1",))`。
- `tests/_runtime/test_runtime.py:636-718` 的断言形如 `MultipleDefinitionError("x", ("0",))`。
- `tests/_ast/test_app.py:331` 和 `:346` 有 `pytest.raises(MultipleDefinitionError)`。
- `tests/_code_mode/test_code_mode_context.py:413` 和 `:427` 测 multiply-defined 的提示文案。
- `registry.definitions` 没有找到专门的单元测试；`tests/_runtime` 下没有 dataflow 子目录。
- 约定：`VariableData.qualified_name` 的注释是“In the sql case, the name may be qualified”。限定名的拼法是 `sql_visitor.py:363` 的 `SQLRef.qualified_name` 属性（我只用 grep 看到行号，没细读）。
- 与题面不冲突，但新接口的返回值形状只能靠接口描述猜。

## 【5 边界与隐含要求】
- 同一个完全限定名在两个 cell 里（如 `a.b.xx` 与 `a.b.xx`）仍要报冲突。
- 无限定名的 `xx` 和 `s.xx` 之间怎么处理，题面说“same unqualified name still is”。这指两个无限定的 `xx` 冲突，但 `xx` 与 `s.xx` 是否冲突没有明说。
- table 与 view 同名同限定名要冲突。现有逻辑对“种类不同”的情况有一个特殊分支（第 59-65 行），要保证不被破坏。
- 一个 cell 里先后定义多个同叶名的限定名（`variable_data[name]` 是列表，而登记只用 `[-1]`），可能漏掉前面的定义。
- 删除 cell 后，剩下那个 cell 的定义不能被一并清掉；叶名下仍有其他限定名的 cell 时，不能 `del self.definitions[name]`。
- 和 Python 变量同名的情形：`kind` 为 `variable` 的 `xx` 与 SQL 表 `s.xx` 之间的冲突要保留。
- 返回的 `set[CellId_t]` 应该只含真正冲突的 cell，而不是叶名下所有 cell。
- `validate_graph.py` 里生成 `MultipleDefinitionError` 时，`cells` 也应只列真正冲突的 cell。

## 【6 改动规模】
- 核心改动在 `definitions.py` 一个文件，大概 3 个方法：`register_definition`、`unregister_definitions`、`get_multiply_defined`。可能需要新增一个按（叶名、限定名）分组的辅助结构。
- 牵连改动约 5-6 个文件：`validate_graph.py`、`app.py`、`_code_mode/_context.py`、`dependency_graph.py`、`to_ir.py`，再加 `graph.py` 的转发签名和相应测试里的 mock。
- 属于局部修补加一处签名变更，不需要贯穿多层，但调用点分散。

## 【7 难点一句话】
难点在于真正的报错来自 `validate_graph.py` 直接读 `definitions`，而接口只点名了 `get_multiply_defined`，所以得自己找出所有判重位置并统一改成按限定名判断，同时保住删除和真实冲突的行为。