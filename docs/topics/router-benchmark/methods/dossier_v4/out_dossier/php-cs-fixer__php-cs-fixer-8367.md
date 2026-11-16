我已经查完主要文件，现在整理档案。

# 仓库档案：`fully_qualified_strict_types` 与箭头函数返回类型

## 【1 题面要点】
- 要求：`import_symbols=true` 时，箭头函数 `fn (): \A\B\C => ...` 的返回类型也要改成短名 `C`，并加入 `use`。
- 现状：`new \A\B\C(...)` 已被缩短，`use` 也已添加，只有 fn 的返回类型 FQCN 没动。
- 复现和期望输出都给了：`fn (): \Symfony\Component\HttpFoundation\JsonResponse => new ...` 应变成 `fn (): JsonResponse => new JsonResponse(true)`。
- 题面没有给修法建议。

## 【2 相关代码】（`src/Fixer/Import/FullyQualifiedStrictTypesFixer.php`）
- `applyFix` 292–399：主循环在 329–370 逐 token 分派。
  - 339 行只判断 `T_FUNCTION` 才调用 `fixFunction`。
  - 全文件没有 `T_FN`（grep 无结果）。这是最可能的根因。
  - 循环分两遍：发现阶段（`discoverSymbolsPhase=true`）收集符号，修复阶段改写 token。
- `isCandidate` 227–242：`T_FUNCTION` 在列表里，`T_FN` 不在。
  - 只含 `fn` 的文件，如果没有 `T_NEW`、`T_VARIABLE` 等其他候选 token，可能整体被跳过。
  - 题面示例有 `T_VARIABLE`，所以不受影响，但这是隐含要求。
- `fixFunction` 619–636：取参数类型和返回类型，交给 `replaceByShortType`。
- `replaceByShortType` 856、`getTypes` 907、`determineShortType` 885：把类型拆成各段，发现阶段登记符号，修复阶段改写。
- `src/Tokenizer/Analyzer/FunctionsAnalyzer.php`
  - `getFunctionReturnType` 157–182：它先找下一个 `(`，再找 `T_TYPE_COLON`。结束位置通过 `getNextTokenOfKind($typeColonIndex, ['{', ';', [T_DOUBLE_ARROW]])` 判断，已经支持 `=>`，所以 fn 能用。
  - `getFunctionArguments` 142–154：同样只用 `(`，对 fn 也成立。

## 【3 并列与牵连】
- 并列分支是 `T_FUNCTION` 的分派和 `isCandidate`，两处都要考虑加 `T_FN`。
- fn 的参数类型目前走的是另一条路：349–353 行的 `T_VARIABLE` 分支，当前一个 token 是 `T_STRING` 时调用 `fixPrevName`。
  - 参数类型是 `\Foo\Bar $a`（带前导反斜杠）时，前一个 token 是 `T_NS_SEPARATOR` 还是 `T_STRING`，需要实测确认。
  - 如果改走 `fixFunction`，参数可能被处理两次，需要确认幂等。
- 其他 fixer 里没有 `T_FN` 的使用（`src` 下的 grep 结果为空），没有现成参考。
- 受影响的可能还有：
  - 发现阶段对 fn 的符号登记（决定 `use` 是否生成）。
  - `reservedIdentifiersByLevel` 的花括号层级计数。fn 没有花括号，应该无影响。

## 【4 现有测试与约定】
- `tests/Fixer/Import/FullyQualifiedStrictTypesFixerTest.php` 的 `provideFixCases` 从 60 行开始，`import_symbols` 用例很多（494、521、553 等）。
  - 我的 grep 里没有出现 fn 用例。该文件的 grep 输出没有 `fn` 行，所以这个文件里目前没有箭头函数用例。
  - 隐藏测试很可能是在这里新增 fn 用例，也可能分 PHP 版本。
- `tests/Tokenizer/Analyzer/FunctionsAnalyzerTest.php` 已覆盖 fn：
  - 参数：483–587 行，如 `fn(\Foo\Bar $a) => null;`。
  - 返回类型：639 行 `fn() => null` 期望 null；667 行 `fn($a): \Foo/** TODO */\Bar => null` 期望 `TypeAnalysis('\Foo\Bar', 7, 11)`。
  - 所以分析器侧不需要改，与题面不冲突。
- 约定：同一规则对 `function` 的返回类型和参数类型已有行为，fn 应与之一致。`getFunctionReturnType` 的内部类型 token 里允许夹注释，这点是已有约定。

## 【5 边界与隐含要求】
- 带参数类型的 fn：`fn(\A\B $x): \A\C => ...`。
- 可空类型 `?\A\B`、联合类型、交叉类型、DNF 类型。
  - `replaceByShortType` 已处理这些，但 fn 的结束位置依赖 `=>`，要确认不会误判。
- 类型里带注释。
- 嵌套 fn，以及 fn 作为参数出现在其他函数调用中。
- `static fn`。
- 返回类型 `static` / `self` 或保留类型不应被改。
- 未启用 `import_symbols` 时，fn 返回类型应缩短到当前命名空间或已有 `use`（修复阶段同路径）。
- 全局命名空间下的 `leading_backslash_in_global_namespace`。
- 两遍循环里 token 数量变化需要 `indexDiff` 修正（369 行已有）。
- fn 在 `$foo = fn` 之类位置出现时的 token 类型。`T_FN` 在 PHP 7.4 以下不存在，可能要用 `\defined('T_FN')` 保护。
  - 仓库的 `T_ATTRIBUTE` 就是这样处理的（231、354 行）。需要确认最低 PHP 版本要求。

## 【6 改动规模】
- 源码只涉及 1 个文件，约 2–3 处：
  - 主循环的分派条件（339 行）。
  - `isCandidate`（227–242 行）。
  - 可能要对 `T_FN` 做版本保护。
- 测试要新增 1 个文件里的几个用例。
- 属于局部修补，不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
- 根因很可能很浅（主循环不识别 `T_FN`），难点在于确认 fn 的参数类型走 `T_VARIABLE` 分支后，再走 `fixFunction` 是否重复处理，以及发现阶段、修复阶段两遍的行为是否一致。

**未验证的地方：**
- 没有实际运行复现，上面关于 `T_FN` 缺失的判断来自读代码和 grep，不是跑出来的。
- `FunctionsAnalyzerTest` 的 fn 返回类型用例我只读到 639–667 行附近，没有逐条看全。