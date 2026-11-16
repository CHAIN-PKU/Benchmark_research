**档案：Extract function 在 `use` 链末尾选区时提取过多**

我查了 `language-server/src/code_action.rs`、`engine.rs`、`tests/action.rs` 和 `compiler-core/src/ast.rs`。这份档案只靠读代码和推理，没有运行复现，所以第 2 节里对根因的判断还没验证过。

## 【1 题面要点】
- 要求的行为：选中函数中间一段（从 `let toml_path` 到末尾的 `simplifile.write(...) |> result.replace_error(...)`）时，只提取选中的部分。
- 实际行为：整个函数体被提取，原函数只剩 `function(target, user_id)`。
- 题面给了：
  - 复现：完整函数加选区起止标记（神似 neovim 选区，终点是最后一行的行尾）。
  - 期望输出：原函数保留前两个 `use ... result.try(...)`，末尾调用 `function(target, user_id)`，新函数含选中的语句。
- 题面没给修法建议，也没给测试。
- 期望输出里有几处瑕疵：
  - 文档注释和一条注释被挪动了位置。
  - 新函数签名被拆成多行。
  - 这些大概只是手写示意，不能当快照精确值。
- 关键句："It will extract the entire function content into a new function"。

## 【2 相关代码】
全在 `language-server/src/code_action.rs`，`ExtractFunction` 在 10386 行起：
- `code_actions` (10559)：访问 AST 后按 `ExtractedValue` 分派到各个 `extract_*` 函数。
- `visit_typed_statement` (11391)：用 `can_extract_statement` 判断，把语句记成 `Statements` 或 `Use`，并合并多条语句的范围。
- `visit_typed_expr` (11364)：用 `can_extract_expression` 判断，只在 `self.function.is_none()` 时记录。
- `can_extract_statement` (11281) 和 `can_extract_expression` (11231)：**最可能的出错点**。
  - `Use` 和 `Assert` 的判据是 `!completely_within(selected_range, statement_range)`（11319-11321）。
  - 表达式（`Call`、`Fn`、`Block` 等）的判据是 `!completely_within(selected_range, expression_range)`（11277）。
- `completely_within`（`engine.rs:1911`）要求四个端点全是严格不等：`a.start > b.start && a.start < b.end && a.end > b.start && a.end < b.end`。
- `Use` 语句的 location 是 `use_.location.merge(&use_.call.location())`（`compiler-core/src/ast.rs:4397, 4428`）。它覆盖 `use` 头部加整个后续块，也就是一直到函数最后一个表达式的末尾。

**推测的根因**（未运行验证）：选区终点正好等于最后一条语句的末尾，也就是外层 `use priv <- ...` 的范围终点。
- `a.end < b.end` 不成立，所以 `completely_within` 为 false。
- 外层 `use` 因此被判定为“可提取”，整个 `use` 链被当成 `ExtractedValue::Use` 提取。
- 相关分派：`ExtractedValue::Use` 走 10702-10712，调用 `extract_code_in_tail_position`；该函数用 `replace(location, call)` 整段替换，这就是原函数只剩 `function(...)` 的原因。
- 对嵌套的 `use _ <- ...`，该语句在 11435-11449 又被当作已有 `Use` 的内部，不会改变结果。

## 【3 并列与牵连】
- 同样的“严格内部”判断出现在多处，都存在终点贴边问题：
  - `can_extract_statement` 里的 `Use | Assert` 分支。
  - `can_extract_statement` 里的 `Assignment` 分支（11332-11333）：`!within(selected, value_range) && !completely_within(selected, statement_range)`。
  - `can_extract_expression` 的表达式分支（11277）。
- 如果改 `completely_within`（`engine.rs`）本身，会波及所有调用者。要先 grep 这个函数在其他 code action（`ExtractVariable`、`ExtractConstant` 等）里的使用，改动前要评估影响。
- `ExtractVariable`（5497 附近）和 `ExtractConstant` 有类似的 use 内选择逻辑，测试名里有 `extract_variable_does_not_extract_use` 等。它们是否有同样的贴边问题，我没有逐个查。
- 起点贴边的对称情况也值得想：选区起点正好在 use 的 `use` 关键字处是“选中整个 use”，这是合法的，见现有测试 `extract_use_inside_function`。

## 【4 现有测试与约定】
- 测试在 `language-server/src/tests/action.rs`，用 `assert_code_action!(EXTRACT_FUNCTION, 代码, 选区)`。常量在第 198 行。
- 与 use 相关的现有测试（12462-12533）：
  - `extract_use_inside_function`：选 `use` 到 `<-`，期望整个 use 被提取。
  - `extract_use_inside_block`：选 `use` 到 `Nil)`。
  - `extract_use_with_some_statements_before`。
  - `extract_use_including_some_statements_after`。
  - 这些都是从 `use` 关键字开始选。
- 没发现有“从 use 链的内部开始选、终点在块尾”的测试，这应该就是需要新增的回归测试。
- 选区助手：`find_position_of(..).select_until(..)`，也有 `under_char` 和 `under_last_char`。注意 `select_until` 的终点是否含最后一个字符，会影响能否复现“终点贴边”。
- 快照是 insta 风格（我没打开 snap 文件确认）。
- 没有外部规范，行为由测试快照约定。
- 与题面期望不冲突：现有测试都是选中整个 `use`，题面是选中 `use` 之后的内部语句。

## 【5 边界与隐含要求】
- 起点在 use 头部之后、终点贴着块尾：应提取内部语句，且这些语句要处于“尾位置”。
  - `visit_typed_statement` 里的 `is_in_tail_position` 取决于 `last_statement_location`。
  - `visit_typed_expr` 遇到 `Fn`（use 回调）会更新该值，最后一条是 `simplifile.write(...) |> ...`，它是 `Pipeline`，在 11415 行会被置为 `None`，改由 pipeline 路径处理。
- **管道语句的特殊处理**：最后一条语句是管道。
  - 11414-11415 对 `TypedStatement::Expression(Pipeline)` 返回 `None`。
  - 选区跨多条语句时，后面的 pipeline 靠 `visit_typed_pipeline_assignment`、`visit_typed_expr_pipeline` 追加。
  - 期望输出要求提取 `let`、`use`、`let`、管道的整体。选区终点在管道最后一步行尾，可能还要保证 `finally` 的 `try_add_pipeline_step` 逻辑不会把范围错误地缩成 `PipelineSteps`。这点需要实测。
- 内部还有 `use gleam_toml <- result.try(...)`：它在选区内，被当作 `Use`，再遇到后面的 `let` 时转成 `Statements`（11442-11450）。合并时的 `position`（尾位置）要正确。
- 参数推断：`target`、`user_id` 是函数参数，在选区外定义，应成为新函数参数。`priv` 没被用到，不该出现。
- 多种选区终点：不在行尾、在行尾（neovim 光标 `$`）、包含末尾换行。
- 期望输出中提取的是从 `let toml_path` 开始的语句，选区起点在注释之后。注释是否带走取决于 `code_at(location)`，一般不带。

## 【6 改动规模】
- 预计只改 `code_action.rs` 一个文件，几行：调整 `can_extract_statement` 和 `can_extract_expression` 里的判据，或新增一个“选区是否落在 use 头部之后的内部”判断。
- 另加一个测试和一份快照文件（`language-server/src/tests/snapshots/`）。
- 局部修补，不需要新增结构，除非要区分 use 头部和 use 体。

## 【7 难点一句话】
难点在于 `Use` 语句的范围覆盖整个后续块，选区终点恰好贴着块尾时 `completely_within` 的严格不等式失效。修复要在不破坏“选中整个 use”这类现有测试的前提下区分“选区在 use 内部”和“选中整个 use”，并保证提取后的尾位置、管道和参数推断都正确。