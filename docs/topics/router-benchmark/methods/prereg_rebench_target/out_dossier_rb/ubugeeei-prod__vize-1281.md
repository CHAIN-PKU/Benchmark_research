【1 题面要点】
- 要求：`@vize:ignore-start` / `@vize:ignore-end` 区域和 `@vize:forget` 必须能压制 template 阶段（`run_on_template`）规则产生的匹配诊断。
- 题面没有复现、期望输出，也没有给修法。关键句："Suppression boundaries, unmatched directives, and later unrelated diagnostics must retain their normal behavior."，另有 "No new interfaces are introduced."
- 隐藏测试大概率仿照 `test_vize_expected_suppresses_run_on_template_diagnostic`。输入是 ignore 区域或 forget 包住 `v-if="a"` / `v-else-if="a"`，断言没有 `vue/no-dupe-v-else-if` 诊断。

【2 相关代码】
- `crates/vize_patina/src/visitor.rs:43-66` `visit_root`：先调用 `prescan_suppression_directives`，再对每条规则跑 `run_on_template`，最后才遍历子节点。
- `visitor.rs:68-115` `prescan_suppression_directives` / `prescan_suppression_in_child`：目前只预注册 `Expected` 和 `Level`。注释（68-73 行）明确写着 IgnoreStart/End 和 Forget 故意不在这里处理。它只递归 `Element` 和 `For`，不进入 `If` 节点。
- `visitor.rs:118-167` `visit_child`：forget 的实际压制发生在这里。`forget_next_element` 为 true 时，对下一个 Element / If / For 调用 `ctx.disable_all(start_line, Some(end_line))`。
- `visitor.rs:170-238` `process_vize_directive`：`IgnoreStart` 调 `push_ignore_region`，`IgnoreEnd` 调 `pop_ignore_region`，`Forget` 在 payload 为空时发 `vize/forget` 警告并置位 `forget_next_element`。
- `crates/vize_patina/src/context.rs:307-342` `report`：依次检查规则是否启用、`is_disabled_at`、expected 行、severity 覆盖。
- `context.rs:346-376` `is_disabled_at`，`context.rs:379-414` `disable_all` / `push_ignore_region` / `pop_ignore_region`：`pop` 关闭最近一个 `end_line=None` 的范围。
- `crates/vize_patina/src/linter/engine.rs:366` 创建 `LintVisitor`。`rule.rs:59` 是 `run_on_template` 的默认空实现。

【3 并列与牵连】
- 并列实现：prescan 与主遍历各自处理指令，修改要两边同步，避免重复登记。
  - 主遍历里 `Expected` / `Level` 目前也会再登记一次。这没问题，因为是 `HashSet` / `HashMap`，幂等。
  - `disabled_all` 是 `Vec`，不幂等。如果 prescan 登记了 ignore-start 区域，主遍历再 push，`pop` 会配对错误或重复。所以必须二选一，或在主遍历里跳过。
- forget 在 prescan 里需要定位"下一个兄弟节点"。预扫描是按父节点的 children 顺序扫的，要在这里完成"注释 → 下一个 Element/If/For"的配对，并算出行范围。
- 注释、元素、If 分支在预扫描阶段可能是已转换的 `If` / `For` 节点，需要确认 `If` 节点的 branches 里也可能有注释，目前 prescan 不递归 `If`。
- 影响面：
  - 所有 `run_on_template` 规则的诊断（如 `vue/no-dupe-v-else-if`、`vue/no-mutating-props`）。
  - `vize/forget`、`vize/todo` 这类指令自己发的诊断仍要保持原行为，所以不能整体提前处理指令。
- 另外 `crates/vize_maestro` 里有 ignore 相关的补全和 code action，仅是 IDE 提示，不涉及逻辑。

【4 现有测试与约定】
- `crates/vize_patina/src/linter/tests/directives.rs:88-108` 是 expected 的 template 阶段回归测试（#968），断言 `.filter(|d| d.rule_name == "vue/no-dupe-v-else-if").count() == 0`。这是最直接的参考。
- `directives.rs:111-123` `test_vize_ignore_start_end_region` 断言 `error_count == 0`。
- `linter/tests/basic.rs:217-292` 是 forget 的测试：
  - `:232` 断言 "Error should be suppressed by @vize:forget"。
  - `:244-246` 断言无 reason 时 `error_count == 0`，且 `diagnostics[0].rule_name == "vize/forget"`。
  - `:262` 断言多行元素整体被压制，`:278` 和 `:292` 断言 v-for 和 v-if 节点被压制。
- 约定：`docs/content/guide/comment-annotations.md` 描述指令语义。`visitor.rs` 的注释说 todo/fixme/forget 等会产生诊断，依赖现有顺序。与题面不冲突。
- 快照测试用 `insta`（directives.rs:15 等），改动不应改变现有快照。

【5 边界与隐含要求】
- 未配对的 `ignore-start`：保持开放到文件末尾；未配对的 `ignore-end`：保持无操作。
- 区域边界：行号包含起止注释所在行，注释之后的无关诊断仍须报出。
- 嵌套的 ignore 区域按栈配对。
- `@vize:forget` 后面没有元素：不应压制任何东西。forget 之后的 text 或 comment 兄弟节点是否跳过要保持与现状一致。
- forget 作用于 `If` 节点时，范围要覆盖整个 v-if / v-else-if / v-else 链，`no-dupe-v-else-if` 报在 else-if 上。
- forget 无 reason 仍要发出 `vize/forget` 警告，且该警告不能被自己压制。
- ignore-start 注释位于嵌套元素内，或在 `If` / `For` 分支内，prescan 需要递归到这些地方。
- 行号与 offset 的转换：prescan 阶段 `ctx.offset_to_line` 可用。
- 同一行的多条诊断都要压制。

【6 改动规模】
- 主要在 `visitor.rs`，可能小改 `context.rs`。
- 局部修补：扩展 prescan，加入 IgnoreStart / IgnoreEnd / Forget 的处理，并让主遍历不再重复登记。
- 不需要新增接口或贯穿多层。

【7 难点一句话】
难在 prescan 与主遍历的两遍处理要避免重复登记 `disabled_all`（`pop` 配对会错），同时 forget 要在 prescan 中准确配对下一节点（包括 If 链）、不破坏 forget 自身警告和边界行为。