# 档案：Extract function 在匿名函数中错误返回 `Nil`

## 【1 题面要点】
- 要求的行为：从匿名函数（`fn() {...}`）里提取最后一条语句时，新函数应该返回该语句的值，不能固定返回 `Nil`。
- 复现代码：
  ```gleam
  fn wibble() {
    let wobble = fn() {
      echo "wibble"
      echo "wobble" // extracting this line
    }
  }
  ```
- 题面给出了错误输出：提取出的函数是 `fn function() -> Nil { echo "wobble"  Nil // this is incorrect! }`。
- 题面没有给期望输出，也没有给修法建议。作者只写了 "I have a fix for it."，并写明 "No new interfaces are introduced."。
- 按文档注释推断，期望输出应是 `fn function() -> String { echo "wobble" }`，调用点是 `function()`。

## 【2 相关代码】
所有相关代码都在 `language-server/src/code_action.rs`。

- `ExtractFunction` 结构体（10301）：
  - 字段 `last_statement_location`（10310）用来判断一条语句是否处于 tail 位置。
  - 注释写明：访问者不会告诉我们某条语句是不是块或函数的最后一条，所以要手动跟踪。
- `StatementPosition { Tail{type_}, NotTail }`（10452）：文档说明 tail 位置不能返回 `Nil`。
- `impl Visit for ExtractFunction`（11254）：
  - `visit_typed_function`（11255）在进入函数时设置 `last_statement_location = function.body.last().location()`。
  - `visit_typed_expr_block`（11266）会保存旧值，设成块的最后一条语句，访问完再恢复。
  - **没有覆盖 `visit_typed_expr_fn`**，这就是根因：进入匿名函数后，`last_statement_location` 仍是外层函数的最后一条语句，所以匿名函数里最后一条语句不被认为是 tail。
  - `visit_typed_statement`（11296）用 `last_statement_location == statement_location` 判断 tail，再决定 `Tail` 或 `NotTail`（11309）。
- `extract_statements`（10895）：
  - 在 `returned_variables` 为空时返回 `(nil, "Nil")`（10964–10965），并追加 `Nil` 行（11001–11005）。
  - 这是症状出现的地方。
  - 同一个 `match extracted.value` 里应该还有处理 `Tail` 的分支，在 10492 之后、约 10600–10620 附近，我没有读完。

## 【3 并列与牵连】
- 匿名函数是缺口。我没有检查 `use` 回调，它们的 body 是 `use_.call` 里的 `fn` 表达式，也会经过 `visit_typed_expr_fn`。
- 修复应是仿照 `visit_typed_expr_block`，新增 `visit_typed_expr_fn` 覆盖：
  - 保存旧值。
  - 设为 `body.last().location()`。
  - 调用 `ast::visit::visit_typed_expr_fn`。
  - 恢复旧值。
  - 默认实现在 `compiler-core/src/ast/visit.rs:1502`。
- 匿名函数的参数是闭包内部变量。`parameters` 和 `returned_variables` 的计算与它交互，在 10492–10890 之间，我没有细读。
- case 分支的 body 是表达式，不是语句列表，不涉及这个机制。
- 仓库中其他 action 也各自覆盖了 `visit_typed_expr_fn`（如 1545、3106、4325），可作为写法参考。

## 【4 现有测试与约定】
- 测试在 `language-server/src/tests/action.rs`，常量 `EXTRACT_FUNCTION`（198），测试从约 11989 到 12769，另有 13378、13406。
- 我没有逐条读断言。测试使用 `assert_code_action!` 加快照。快照文件在 `language-server/src/tests/snapshots/` 下。我没有打开快照。
- 已有的测试名没有任何一个包含 anonymous、fn、closure 或 tail，因此匿名函数这种情况没有测试覆盖。
- 约定来自 `ExtractFunction` 的文档注释（10410–10450）：tail 位置的语句，被提取后新函数必须返回最后的值。
- 隐藏测试大概是新增一个快照测试，输入就是题面的例子。题面的期望与现有约定不冲突，只是实现遗漏。

## 【5 边界与隐含要求】
- 嵌套多层匿名函数：必须在退出内层后恢复外层值。
- 匿名函数在表达式位置，例如作为参数（`list.map(xs, fn(x) { ... })`）。
- 匿名函数内选中的是中间语句，应仍然返回 `Nil`。
- 匿名函数内选的是多条语句，包含最后一条。
- 匿名函数的 tail 是 `use` 语句（`statement.is_use()` 已单独处理）。
- 选中范围跨越匿名函数边界，这是已有的部分选择逻辑。
- 现有函数 `visit_typed_function` 只在选区在函数内时才进入。匿名函数不需要检查选区，只要正确维护 tail 位置即可。

## 【6 改动规模】
- 只需改一个文件的一处：新增一个约 15–20 行的 `visit_typed_expr_fn` 覆盖。
- 再加一两个测试和对应快照。
- 属于局部修补，没有新增结构，也不贯穿多层。
- 需要引入的类型（`FunctionLiteralKind`、`TypedArg`、`Vec1` 等）在同文件的其他 visitor 里已经导入，可以直接复用。

## 【7 难点一句话】
定位本身很直接，难点在于补全 `visit_typed_expr_fn` 时保存和恢复 tail 位置要写对，再确认快照输出（返回类型、缩进）和隐藏测试逐字一致。