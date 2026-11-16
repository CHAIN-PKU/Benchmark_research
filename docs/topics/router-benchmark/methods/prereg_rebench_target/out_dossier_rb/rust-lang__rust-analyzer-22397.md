**【1 题面要点】**
- 要求的行为：`foo!(bar$0)` 要补全出 `bar!`。`foo!` 的参数是 `$i:ident`，展开后是 `$i!()`，也就是宏调用里的宏路径。
- 题面只给了复现代码，没有期望输出，也没有修法建议。
- 复现代码如下（`$0` 是光标）：
  ```
  macro_rules! bar { () => (); }
  macro_rules! foo { ($i:ident) => { $i!() }; }
  fn main() { foo!(bar$0); }
  ```
- "Interface" 一节写着 "No new interfaces are introduced"，所以不会有新的公开 API。
- 我没有运行代码，下面关于根因的判断都是读代码推断出来的。

**【2 相关代码】**（都在 `crates/ide-completion/src/context/analysis.rs`）
- `expand_maybe_stop`（132–170）：对展开后的文件递归处理。
  - 先调用 `expand`。
  - 如果 `expand` 返回 None，再用 `sema.is_inside_macro_call` 判断原 token 是否已不在宏调用里。不在则返回递归基例，否则返回 None。
  - 这里最可疑：展开结果 `bar!()` 里的 `bar` 本身在 MacroCall 路径中，`is_inside_macro_call` 是向上找任意 `ast::MacroCall` 祖先（`crates/hir/src/semantics.rs:1089-1111`），会直接返回 true。于是基例不成立，整条链返回 None，补全落空。
  - 这是我的推断，没有验证。
- `expand`（172–438）：
  - 第 257–262 行用 `ancestors_at_offset(...).map_while(TokenTree/Meta).last()?` 找 token tree。展开后的 `bar!()` 里，光标在路径上而不在 token tree 里，这里就返回 None。
  - 随后在 380–437 行展开 fn-like 宏调用。
- `analyze` 里的 `kind_macro_call`（1484–1499）：把 `ast::MacroCall` 路径转成 PathKind。
  - 先试 `kind_item`（1450–1481）。它只认 ItemList、AssocItemList、ExternItemList、SourceFile 这几种父节点。
  - 再看父节点是不是 MacroExpr、MacroPat 或 MacroType，其他情况 `return None`。
  - 宏展开成语句时，根节点可能是 MACRO_STMTS，`bar!()` 的父节点不在上述几类里，那这里也会返回 None。这同样是推断。
- 调用点：1570 行（`ast::MacroCall`）和 1599 行（路径限定符内部）。
- `crates/ide-completion/src/render/macro_.rs:15-59`：有 `has_macro_bang` 时不再补 `!`。此处 `bar!()` 已有感叹号，应当不补。

**【3 并列与牵连】**
- `kind_macro_call` 有两个调用点（1570 和 1599），改它会同时影响限定路径 `a::b!()`。
- `expand_maybe_stop` 在三处被调用：属性展开（235）、derive helper（356）、fn-like（421）。改基例判断会影响全部三条路径。
- 如果改 `semantics.rs` 的 `is_inside_macro_call`，它还有别的使用者，我没有全部排查。
- 另外，`ExpansionResult` 在 `expand_maybe_stop` 里 `derive_ctx` 固定为 None。

**【4 现有测试与约定】**
- `crates/ide-completion/src/tests/special.rs:470`：`completes_in_simple_macro_call`，对应的宏是 `macro_rules! m { ($e:expr) => { $e } }`，输入 `m!(self::f$0);`，断言补全出 `fn foo()` 和 `fn main()`。这是"宏参数里补全"的现有写法。
- 同一文件还有 `completes_qualified_macros`（371）、`completes_macro_segment`（485）、`completes_in_macro_body`（666）、`completes_locals_from_macros`（1063）。
- 其他相关测试：`tests/expression.rs:807`（`in_macro_expr_frag`）、`tests/item_list.rs:715`（`tokens_from_macro`）。
- 隐藏测试大概率是在 `special.rs` 或 `expression.rs` 里新增一条用例，输入就是题面的代码，用 `expect![[...]]` 断言列表里含 `ma bar!(…)`。我没有查到官方规范文档，只有仓库内的这些约定，与题面期望不冲突。

**【5 边界与隐含要求】**
- 要补全的位置可能是语句、表达式、模式、类型或 item 位置，展开结果的位置不一定都能走通。
- 只补全 fn-like 宏，不能把属性宏和 derive 宏列出来。
- 展开里已经有 `!`，所以不应再插入 `!()`。
- 不能破坏现有"宏参数里补全普通标识符"的行为。基例判断一旦放宽，可能让本该继续展开的情形提前停下，或者反过来。
- 补全标记 `COMPLETION_MARKER` 附加在 `bar` 之后，展开时 `$i` 的 token 映射和偏移补偿要对得上。

**【6 改动规模】**
- 估计 1 个文件，2 到 3 处（`analysis.rs` 里的基例判断和/或 `kind_macro_call`），外加新增 1 到 2 条测试。
- 属于局部修补，不需要新增结构。如果要改 `hir` 里的 `is_inside_macro_call`，会多涉及一个 crate。

**【7 难点一句话】**
难在先定位失败发生在哪一环：是 `expand` 的 `?` 提前退出、`is_inside_macro_call` 把展开结果里的 MacroCall 路径误判为"仍在宏调用输入里"，还是 `kind_macro_call` 在 MACRO_STMTS 父节点下返回 None。修法一旦放宽，还要避免影响其他展开路径。