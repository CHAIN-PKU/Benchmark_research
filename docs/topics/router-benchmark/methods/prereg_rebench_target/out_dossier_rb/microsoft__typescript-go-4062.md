我已查完，现在整理档案。

# 仓库档案：isolatedDeclarations 下对象字面量方法的 `this` 参数

## 【1 题面要点】
- 要求的行为：在 `--isolatedDeclarations` 下，对象字面量方法只要返回类型和参数都有显式标注，就不应报错。
- 复现代码：
  ```ts
  export function fromProviders<T>() { return { tearDown(this: {state: T}): void {} }; }
  ```
- 期望：与 TS 6.0 一致，没有错误，并输出 `tearDown(this: { state: T; }): void;`。
- 实际：tsgo 报 `error TS9008: Method must have an explicit return type annotation with --isolatedDeclarations.`
- 题面没有给修法建议。"Interface" 一节写的是 "No new interfaces are introduced"。
- 题面标题和内容都提到泛型，但没说明泛型是否是触发条件。

## 【2 相关代码】
以下是我读代码推断的根因，没有运行验证。
- `internal/checker/pseudotypenodebuilder.go:446-468`（`PseudoObjectElementKindMethod` 分支）：比较伪类型和真实类型时，先比参数个数 `len(targetSig.parameters) != len(d.Parameters)`，不等就调用 `ReportInferenceFallback(e.Name.Parent)` 并返回 false。后面的 `targetSig.parameters[i]` 是按下标对应的。
- `internal/pseudochecker/lookup.go:691-717`（`cloneParameters`）：把声明里所有参数都克隆进伪参数列表，包括名为 `this` 的参数。
- `internal/checker/types.go:1268`：checker 的 `Signature` 把 `this` 单独放在 `thisParameter`，不在 `parameters` 里。因此伪参数多一个，个数对不上，就退化成推断并报错。
- `internal/checker/pseudotypenodebuilder.go:530-557`（`SingleCallSignature` 分支，用于函数表达式和箭头函数）有同样的个数和下标比较，`this` 参数同样会错位。
- 序列化也要看：
  - `pseudotypenodebuilder.go:231` 和 `:243` 通过 `pseudoParametersToNodeList(d.Parameters)` 输出参数，`:300-325` 是它的实现和 `pseudoParameterToNode`。
  - `pseudoParameterToNode` 用 `p.Name.Parent.Symbol()` 取参数名。`this` 参数的名字节点是否能正常序列化，需要确认。
  - `:208-210` 的 `enterNewScope` 传入 `getExpandedParameters`，也要确认 `this` 在其中如何处理。
- 报错的出口：`internal/transformers/declarations/tracker.go:56-68`（`ReportInferenceFallback`）→ `diagnostics.go:664-702`（`createGetIsolatedDeclarationErrors`，`KindMethodDeclaration` 走 `createReturnTypeError`）→ `diagnostics.go:492` 给出 TS9008。
- 关于"泛型"：`this: {state: T}` 里的 `T` 来自外层函数，与伪类型比较无直接关系。个数不等的路径对非泛型 `this` 参数应该同样触发，所以泛型很可能不是必要条件。这一点没有验证。

## 【3 并列与牵连】
- 并列实现有三处，都需要对 `this` 做同样的处理：
  1. 对象字面量方法（`pseudotypenodebuilder.go:453-468`）。
  2. 函数/箭头表达式（`:530-557`）。
  3. 伪类型构造处（`lookup.go:344` 和 `:530` 的 `cloneParameters` 调用）。
- 如果在 `cloneParameters` 里过滤掉 `this`，序列化就会丢掉 `this` 参数，与 TS 6.0 期望的输出不符。更可能的做法是：比较时跳过 `this`，序列化时保留。
- 其他会受影响的地方：
  - `pseudochecker/type.go:188` 和 `:269`（`NewPseudoTypeSingleCallSignature` / `NewPseudoObjectMethod`）的参数结构。
  - `internal/ls/codeactions_fixmissingtypeannotation.go` 有基于 TS9008 的 code fix，行为可能随之变化。
- 我没有逐个确认还有哪些下游也依赖"伪参数个数 = 真实参数个数"。

## 【4 现有测试与约定】
- 现有 baseline 位于 `testdata/baselines/reference/submodule/compiler/isolatedDeclarationErrors*`，另有 `internal/fourslash/tests/gen/codeFixMissingTypeAnnotationOnExports*_test.go`。
- 我在 `testdata/tests/cases/compiler` 里按 `isolatedDeclaration*.ts` 搜 `this:`，没有找到相关用例，说明 `this` 参数在 ID 下目前基本没有覆盖。
- 隐藏测试很可能是新增一个编译器 baseline 用例，内容就是题面的代码。断言是：无 TS9008，且 `.d.ts` 输出含 `this: {state: T;}`。
- 现有 baseline 的 `.js.diff` 反映与 Strada 的差异。参考实现是 TS 6.0 / Strada 行为，与题面期望不冲突。
- 我没有读到明确的 `this` 参数断言，也没找到仓库内专门针对它的约定。

## 【5 边界与隐含要求】
- `this` 参数不计入 `targetSig.parameters` 的个数与下标，所以跳过 `this` 之后，其余参数的下标要重新对齐。
- 除了个数，还应校验 `this` 的类型是否和 `signature.thisParameter` 一致（若要保持语义严格）。
- 没有标注类型的 `this` 参数（`this` 无类型）应继续报错。
- `this` 参数后面还跟其他参数、可选参数、泛型方法等组合。
- 箭头函数没有 `this` 参数。函数表达式有。
- 类方法（不走 pseudochecker 的对象字面量路径）应当本来就不受影响，建议核对。
- JS 文件里的 `this` 相关 JSDoc（`@this`）不在本题范围，`nodebuilderimpl.go:2020` 附近有注释掉的 `thisTag` 代码。
- 序列化 `this` 参数时，`pseudoParameterToNode` 对 `this` 名字节点的处理需要确认能否正常输出。

## 【6 改动规模】
- 源码约 1-2 个文件（以 `internal/checker/pseudotypenodebuilder.go` 为主，可能连带 `internal/pseudochecker/lookup.go`），涉及 2-3 处。
- 属于局部修补，不需要新增结构，也不贯穿多层。
- 另需新增一个测试用例及其 baseline，baseline 文件由测试工具生成。

## 【7 难点一句话】
难点在于定位：错误信息指向"返回类型"，而真正的原因是伪类型比较时 `this` 参数让参数个数和下标错位；修的时候还要在比较中跳过 `this`、在序列化中保留 `this`，并覆盖对象方法和函数表达式两条并列路径。