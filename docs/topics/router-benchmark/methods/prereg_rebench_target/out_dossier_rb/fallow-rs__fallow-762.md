**档案：unused-class-members FP，Svelte 模板成员调用（以下均已在快照中查证）**

**【1 题面要点】**
- 要求：Svelte `<template>` 里写 `resultState.pin(...)` 这类 `<local>.<method>(...)` 调用时，只要 `<local>` 能解析为某个类的实例，就给该类的方法记一次使用。
- 原文：“credit a method called as `<local>.<method>(...)` inside a Svelte `<template>` when `<local>` resolves to an instance of the class, parallel to the existing Vue/Angular template member-access tracking.”
- 复现只给了项目名 asciimoo/hister：`ResultState.onOpen/.pin/.updateLabel/.addSkipRule`，调用点在 `ResultActionsMenu.svelte`。
- 没有给最小复现，没有期望输出，也没有修法建议。
- 题面没说 `resultState` 在脚本里怎么来。它可能是 `$props()` 解构、`getContext`、从别的文件 import 的单例，或者 `new ResultState()`。这是最大的信息缺口。
- “Interface: No new interfaces”，说明不加公开 API。

**【2 相关代码】**
Svelte 模板成员调用的管线大半已经存在：
- `crates/extract/src/sfc.rs:217` `parse_sfc_to_module`：先走脚本，再调 `apply_template_usage`。
- `sfc.rs:306-386` `merge_script_into_module`：
  - 第 368-383 行，当 `is_template_visible_script` 为真时，把 `extractor.binding_target_names()` 灌进 `template_visible_bound_targets`，并过滤掉 `this.` 开头的键。
  - 第 538 行，Svelte 下只要不是 `context="module"` 的脚本都可见。
- `sfc.rs:502-536` `apply_template_usage`：把模板产生的 `member_accesses` 并入 `combined`。
- `crates/extract/src/sfc_template/svelte.rs:77` `collect_template_usage_with_bound_targets`：各处标签、属性、`{expr}`、`{#each}` 都走 `merge_expression_usage_allow_dollar_refs_with_bound_targets`。
- `crates/extract/src/template_usage.rs:79-170` `analyze_template_snippet_with_bound_targets`：
  - 把片段包装后解析，找未解析的标识符，用 `remap_object_name`（第 221 行）把 `counter` 映射成 `Counter`。
  - 第 88 行有早退：`imported_bindings` 与 `bound_targets` 都为空时直接返回。
- `crates/extract/src/visitor/visit_impl.rs`：`binding_target_names` 的写入点。它决定了哪些脚本局部变量能被认出是类实例，我判断缺口最可能在这里：
  - 第 1992-1996 行：只处理 `BindingIdentifier` 加类型标注，即 `let x: Foo`。
  - 第 2052-2061 行：`const x = new Class()`。
  - 第 2063-2075 行：`const [x] = wrapper(() => new C())`。
  - 第 2087-2098 行：静态工厂候选。
  - 第 1472 行：函数形参的类型标注。
  - 第 1497-1510 行：类属性。
- `crates/extract/src/visitor/mod.rs:475-494` `record_exported_instance_bindings`：导出的实例用 `INSTANCE_EXPORT_SENTINEL` 做跨文件映射。

**【3 并列与牵连】**
- Vue 用的是并列实现 `sfc_template/vue.rs:32`，走同一套 `bound_targets`。Angular 另走 `collect_unresolved_refs_and_accesses`（`template_usage.rs:181`）。
- 如果要扩展“什么算类实例绑定”，改的是 `visit_impl.rs` 里共享的访问器。Vue 和 `.gts`/`.gjs` 也会受影响，所以需要保证不引入误判。
- 成对点：模板侧的 `locals` 遮蔽逻辑（`svelte.rs:600 current_locals`）。
- 下游：`member_accesses` 进入图构建后，由 unused-class-members 检测消费。我没读该检测，建议下一步确认。
- 另一条跨文件路径：如果 `resultState` 是 import 来的，模板里只会产生 `object=resultState` 的访问，要靠导入解析加 `INSTANCE_EXPORT_SENTINEL` 才能到类。

**【4 现有测试与约定】**
- `svelte.rs:938-961` `event_handler_arrow_member_access_maps_script_instance_to_class`：
  - 输入 `<button onclick={() => counter.bump()}>{counter.value}</button>`，绑定 `counter→Counter`。
  - 断言 `access.object == "Counter" && access.member == "bump"`，`value` 同理。
- `svelte.rs:964-987`：`{#each rows as counter}` 遮蔽脚本绑定，`other.go()` 仍映射到 `Other`。
- `vue.rs:626` 和 `vue.rs:652` 有同构测试。
- `crates/extract/src/tests/sfc.rs` 里有 Svelte 端到端测试，例如第 368 行的 namespace 访问。我没有找到“脚本实例加模板调用”的端到端测试。
- `crates/core/tests/integration_test/angular_template_members.rs` 可作为集成测试范本。
- 这和题面期望不冲突。单元层“绑定已知”时已经能工作，所以真正的失败应该出在“绑定不被识别”上。

**【5 边界与隐含要求】**
- 绑定来源要覆盖到 hister 的真实写法。我没看到 hister 源码，以下几种都可能：
  - `let { resultState }: { resultState: ResultState } = $props()`：解构加整体类型标注，目前不会被记录。
  - `let { resultState } = $props<{...}>()`。
  - `const resultState = getContext<ResultState>(key)`。
  - 从 `.svelte.ts` 导入的单例。
  - `$state(new ResultState())`：`new` 被包在调用里，目前不会被识别。
- 遮蔽：`{#each}`、`{#snippet}` 参数、`{@const}` 不能误记。
- `<script context="module">` 的绑定不可见（已有测试）。
- 方法在子组件里经 prop 传下去再调用：题面不要求。
- 避免把同名但类型不同的变量误记（`binding_target_names` 本来就不感知作用域）。
- 缓存：`ModuleInfo` 有缓存序列化（`cache/`）。如果新增了字段，要改 `cache/types.rs`、`conversion.rs` 和大量 `tests.rs` 构造点（约 40 处）。仅扩展识别逻辑则不用。

**【6 改动规模】**
- 最小版：在 `visit_impl.rs` 增加 1-2 种绑定识别，约 1 个文件、几十行，再加几个测试。
- 如果还要走跨文件实例导入，会牵涉图构建层，多层贯穿。
- 总体偏局部修补，但前提是先定位到真实的缺口形态。

**【7 难点一句话】**
Svelte 模板到类的映射管线已经存在并有单测，难点在于推断 hister 里 `resultState` 到底是哪种绑定形态（`$props()` 类型标注、`$state(new …)`、`getContext` 或导入的单例），再把它在脚本访问器里补上，而且不能让别的框架误报或漏报。