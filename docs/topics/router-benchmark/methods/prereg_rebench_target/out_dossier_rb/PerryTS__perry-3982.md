# Perry #3982 仓库档案：namespace 读取内置模块缺失导出应返回 `undefined`

## 【1 题面要点】
- **要求的行为**：`import * as dnsPromises from "node:dns/promises"; dnsPromises.ADDRCONFIG` 应当能编译，并且求值为 `undefined`。其他 strict 原生模块 namespace 上，"只读取值"的缺失属性也应遵循普通 JS 属性语义。
- **要保持的行为**：
  - 命名导入 `import { ADDRCONFIG } from "node:dns/promises"` 仍然被拒绝，与 Node 的 ESM 行为一致。
  - 真正不支持的 API 调用（如 `fs.notARealMethod()`）仍然报 Perry 的 unimplemented-API 错误。
- **复现与期望输出**：题面给了完整的复现和期望输出。
  - `perry check test-parity/node-suite/dns/constants/error-aliases.ts` 报 `error[U006]: dns/promises.ADDRCONFIG is not implemented in Perry ... (#463)`。
  - 绕过 gate 后，运行时输出是 `dnsPromises.ADDRCONFIG: undefined`，与 Node 一致。
- **修法建议**：只有一句定位，没有具体方案：
  - 原文："The relevant gate is in `crates/perry-hir/src/lower/expr_member.rs`: namespace `PropertyGet` on a `NativeModuleRef(module)` fails whenever `module_has_symbol(module, prop)` is `None`…"
- **验收条件**：
  - 上述 `perry check` 无需 `PERRY_ALLOW_UNIMPLEMENTED` 即可通过。
  - 命名导入探针仍被拒绝。
  - 要"add or keep a regression test"来区分"属性读取"与"真实不支持的方法调用"。
- **接口**：无新增接口。

## 【2 相关代码】
- `crates/perry-hir/src/lower/expr_member.rs:1721-1832`：属性读取的 unimplemented gate，是主要改动点。
  - 触发条件：`object` 是 `Expr::NativeModuleRef(module)`，`member.prop` 是 `Ident`，并且 `!allow_unimplemented && !obj_is_named_import && module_has_any_entries(module) && module_has_symbol(module, prop).is_none()`。
  - 满足条件时用 `lower_bail!` 报错，或经 `try_defer_refusal` 延迟（#2309 tree-shaking）。
  - `obj_is_named_import`（1765-1809）通过 `lookup_native_module` 判断是否为命名导入。
- `crates/perry-hir/src/lower/expr_call/native_module.rs:1292-1332`：`mod.method()` 两层调用的 gate，错误文案相同。
  - 之后 1351 起生成 `NativeMethodCall`。
- `crates/perry-hir/src/lower/expr_call/nested_namespace.rs:323`、`:377`：3 层 `mod.X.Y()` 的 gate，包括 `util.types` 和 `dns.promises`。
- `crates/perry-hir/src/lower/expr_call/module_class_static.rs:90`：类静态调用的 gate。
- `crates/perry-api-manifest/src/lib.rs:193`：`module_has_symbol`，按名字或 `class_filter` 匹配，会自动剥掉 `node:` 前缀。
- `crates/perry-api-manifest/src/lib.rs:~218`：`module_has_public_named_export`，命名导入校验用，不受本题影响。
- `crates/perry-api-manifest/src/lib.rs:~210`：`module_has_any_entries`，决定模块是否处于 strict 模式。
- `crates/perry-codegen/src/expr/literals_vars.rs:289`：`typeof nativeModule.member` 的折叠。`None` 时走通用路径。
- `crates/perry-hir/src/lower/unimpl_hints.rs`：`module_member_hint`，为错误信息附加提示。

## 【3 并列与牵连】
- **并列 gate 共 4 处，文案相同**：属性读取（expr_member）、两层调用（native_module）、三层调用（nested_namespace）、类静态（module_class_static）。
  - 只需放宽"属性读取"这一处。
  - 调用 gate 必须保留，题面明确要求。
- **关键风险：调用 callee 是否会再经过 `expr_member` 的 gate。**
  - 某些调用路径可能先把 callee 当作成员读取来 lower。
  - 一旦放宽读取 gate，`fs.notARealMethod()` 可能漏过。
  - 需要确认调用路径在进入 `lower_member` 之前就已经由自己的 gate 拦下。
  - 或者读取 gate 需要知道"当前是不是 callee"。
- **牵连的已有行为**：
  - `perry check` 的 U006 诊断和 `PERRY_ALLOW_UNIMPLEMENTED` 逃生口。
  - `try_defer_refusal` 的 tree-shaking 延迟。
  - `unimpl_hints` 提示。
  - 通过 NativeModuleRef 读取的所有 strict 模块（crypto、axios 等），行为面很广。
- **codegen 对缺失属性的处理**：
  - PropertyGet 在 codegen 对未知属性会得到 `undefined`（题面称绕过 gate 后输出一致）。
  - 个别模块（如 fs、process）的 codegen 路径可能对未知属性有其他行为，需抽查。
- `dns.ADDRCONFIG` 在 fixture 里是存在的（`dns` 导出这些常量），只有 `dns/promises` 缺失。crates 里 grep 不到 `ADDRCONFIG`，说明它的支持在别处（manifest 条目文件 `entries.rs` 之类）。

## 【4 现有测试与约定】
- `crates/perry-hir/tests/unimplemented_api_check.rs:172-180`：
  - `crypto_unknown_method_is_rejected`：`import * as crypto from "crypto"; const x = crypto.foobar;`，断言 `result.is_err()`。
  - **这是纯属性读取，被断言必须报错，与题面期望直接冲突。**
- 同文件 `:234-246`：`supported_module_with_unknown_member_is_rejected`：`axios.foo`，断言 `err.contains("axios.foo") && err.contains("not implemented")`。同样是纯读取，冲突。
- 同文件 `:261-318`：`every_supported_module_rejects_bogus_member`：
  - 对 `NATIVE_MODULES` 里每个模块，`const x = m.__perry_known_bogus_member_513__;` 必须 `Err`，且错误含 `"not implemented"` 和 `"#463"`。
  - 这是覆盖面最大的冲突点。放宽读取 gate 后这条测试必然失败，必须改写。
- 同文件 `:327-364`：`every_supported_module_rejects_bogus_call`（`m.bogus()` 形式）。
  - 这条应该继续成立，可作为"区分读取与调用"的回归测试。
- `crates/perry-hir/tests/util_types_lowering.rs:95`：`util.types.notReal()` 的调用 gate 断言 `"`util.types.notReal` is not implemented in Perry"`。
- `crates/perry-hir/tests/node_named_export_hygiene.rs`：
  - `:23 invalid_node_named_imports_are_rejected`
  - `:141 valid_node_named_imports_keep_compiling`
  - 命名导入由单独机制校验，与本题互不干扰。
- **约定与规范**：
  - Node/ESM 规范：namespace 读取缺失属性返回 `undefined`，命名导入缺失则 SyntaxError。
  - 测试里还有 `perry-codegen/tests/manifest_consistency.rs`（manifest 一致性）和 `test-parity/node-suite` 的 Node 对照夹具。
- **冲突结论**：
  - 现有测试把"读取缺失成员报错"当作契约。题面要求改变这一契约，所以旧断言要改。
  - 隐藏测试很可能把这些读取用例改为"应该通过"，同时保留调用的拒绝用例。
  - 具体放宽到什么范围（所有模块还是只有部分）题面没说清楚，是歧义点。

## 【5 边界与隐含要求】
- "所有 strict 模块"都放宽，还是只对 Node 内置（`node:` 内置）放宽？
  - 非 Node 的原生模块（axios 等）读取 `axios.foo` 现在被测试要求报错，题面只谈"Node built-in"。
  - 若只对 Node 内置放宽，需要用 `is_node_core_module`（lib.rs 里有）来区分，并让 `every_supported_module_rejects_bogus_member` 的断言按模块类别分流。
- **只读 vs 调用的判定**：
  - 属性读取在 callee 位置时需要仍然报错。
  - `typeof`、`in`、可选链、赋值目标、`delete`、`obj.x.y`（读取后继续取成员）等位置语义不同。
  - 例如 `dnsPromises.ADDRCONFIG.foo` 在 Node 里会抛 TypeError，而不是被静态拦下。
- 命名导入后的成员访问（`obj_is_named_import`）已被跳过 gate，不要破坏。
- `dns.promises.ADDRCONFIG` 这种嵌套 namespace 的读取，行为要与 `dnsPromises.ADDRCONFIG` 一致。
- `PERRY_ALLOW_UNIMPLEMENTED` 逃生口行为保持不变。
- 动态 `m["x"]` 访问有单独的 #503 拒绝逻辑，不受影响，但不应被改坏。
- 运行时必须真正返回 `undefined`（而不是 `0.0` 哨兵或 NaN-box 异常）。
  - 题面声称 dns/promises 确实如此，但其他模块（如 process、fs）不一定。
  - `typeof m.absent` 应为 `"undefined"`。
- 如果在 manifest 里加"负面条目"来表示"有意缺失"，要避免影响 `module_has_public_named_export`。

## 【6 改动规模】
- **源码**：1 个主文件、几十行以内的局部修补。
  - 在 `expr_member.rs:1810-1831` 的 gate 上增加"仅当这是调用 callee 或非读取位置才拒绝"的判断，或者直接去掉读取 gate。
  - 若采用"callee 感知"方案，可能要在 lower 调用路径把上下文标志传进来（类似已有的 `suppress_stdlib_dispatch_guard_once` 一次性标志），多触及 `expr_call` 的 1-2 个文件。
- **测试**：2-3 个测试文件。
  - 改写 `unimplemented_api_check.rs` 中 3 个以上读取断言。
  - 新增 dns/promises 的读取通过、命名导入仍拒绝、方法调用仍拒绝的用例。
- 总体：局部修补，不新增结构，也不贯穿多层。

## 【7 难点一句话】
难点在于判断出哪些读取位置可以放行：必须让 `dnsPromises.ADDRCONFIG` 之类的纯读取变成 `undefined`，同时不让 `fs.notARealMethod()`（可能经由同一个成员 lower 路径）漏过去，还要重写与之直接冲突的现有"读取必须报错"测试，并决定放宽范围（所有 strict 模块还是只有 Node 内置）。