查证已经够了（读了约 12 处代码和测试），下面直接给档案。

# 仓库档案

## 【1 题面要点】
- 要求的行为：同时传 `values` 和 `shouldUnregister: true` 时，表单能正常提交，`values` 里的数据不能在首次渲染后丢失。
- 题面只有一句期望：“It is possible to successfully submit a form, when data is provided via `values`, and `shouldUnregister: true` option is set”。
- 复现只有 codesandbox 链接（无法访问）和“Simply submit a form / See error”。没有期望输出，也没有修法建议。
- 题面没说“error”具体是什么。从代码推断，提交的数据是 `{}` 或缺字段，或者校验报 required。
- 版本 7.71.2。接口无变化。

## 【2 相关代码】
- `src/useForm.ts:153-167`：`props.values` 的 effect。值变化时调用 `control._reset(props.values, {keepFieldsRef: true, ...resetOptions})`，然后 `_setValid()`，并更新 `_values.current`。
  - 首次挂载一定会触发这个 reset，因为 `_values.current` 初始为 undefined。
- `src/logic/createFormControl.ts:1615-1758` 的 `_reset`：
  - `:1677-1681`：`_formValues = _options.shouldUnregister ? (keepDefaultValues ? clone(_defaultValues) : {}) : clone(values)`。
    - 开了 `shouldUnregister` 就把 `_formValues` 清成 `{}`。这是最可能的根因：`values` 的数据被丢掉了。
  - `:1665-1671`：`keepFieldsRef` 分支对 `_names.mount` 里的字段 `setValue`。但这发生在 `_formValues` 被覆盖之前，所以会被覆盖掉。
  - `:1692-1701`：`_names` 整体清空，`mount` 变成空 Set。
  - `:1703-1709`：`_state.mount` 取决于 `shouldUnregister`。`:1709` 设 `_state.watch = !!shouldUnregister`。
- `createFormControl.ts:158-160`：初始 `_formValues` 在 `shouldUnregister` 时为 `{}`，否则是 `_defaultValues` 的克隆。
  - `:154-157`：`_defaultValues` 在没有 `defaultValues` 时取自 `values`。
- `createFormControl.ts:358-386` `updateValidAndValue`：字段注册时从 `_formValues`、再退到 `_defaultValues` 取值，并写回 `_formValues`。
  - 重新注册后能否恢复值，取决于这里和 `_defaultValues` 的状态。
- `createFormControl.ts:1387-1414` `register`：已存在的 field 且未 `shouldRevalidateRemount` 时不会走 `updateValidAndValue`。
  - reset 用 `keepFieldsRef` 保留了 `_fields`，所以字段重渲染时可能不会把值写回 `_formValues`。这是候选机制之一。
- `createFormControl.ts:1480-1482`：卸载时加入 `_names.unMount`。`:711-723` `_removeUnmounted`：对非 live 的 ref 调 `unregister`，同时在 `useForm.ts:180` 和 `useWatch.ts:349` 被调用。
- `createFormControl.ts:1516-1527` `handleSubmit`：`fieldValues = cloneObject(_formValues)`，所以 `_formValues` 为空就提交空数据。
- `src/useForm.ts:135-140`：`shouldUnregister` 的 effect，会发一次 `values: _getWatch()`。
- `createFormControl.ts:730-749` `_getWatch`：依据 `_state.mount` 在 `_formValues` 和 `_defaultValues` 之间选。

## 【3 并列与牵连】
- `reset()`（`:1760`）也走 `_reset`，所以改 `_reset` 的 `shouldUnregister` 分支会影响所有 `reset(values)` 调用。
  - 现有 `reset.test.tsx:992` 期望：`shouldUnregister` 下 reset 之后只返回已注册的输入（提交得到 `{}`）。这与“reset 后保留值”的方向有冲突风险。
- `_resetDefaultValues`（`:1799`）：异步 `defaultValues` 也调 `reset`，同样受影响。
- `useController.ts:194-243` 和 `useFieldArray.ts:428-448`：各有自己的 `shouldUnregister` 卸载逻辑。
  - 受控字段和 field array 的值也要一起正确，`_getFieldArray`（`:751-760`）里也有 `shouldUnregister` 分支。
- 并列的入口：`values` prop（`useForm.ts`）、`defaultValues` 异步、`reset(values)`。修复应当只限定在 `values` 的场景，或者在 `_reset` 里区分。

## 【4 现有测试与约定】
- `reset.test.tsx:992-1035`：`reset` 在 `shouldUnregister: true` 下提交结果 `expect(submittedData).toEqual({})`。当前约定是 reset 后清空 `_formValues`，字段重新注册才回来。
- `reset.test.tsx:1037-1081`：`shouldUnregister` 下 reset 后受控和非受控输入的值要正确更新。
- `reset.test.tsx:1083`：条件挂载的受控字段在 `shouldUnregister` 下保留 reset 值。
- `useForm.test.tsx:2255-2339`：`values` prop 的测试（异步加载、`keepDirtyValues`），断言的是 DOM 里 input 的值。
  - 我没有找到 `values` 与 `shouldUnregister` 同时出现的现有测试，所以很可能没有覆盖。
- `useForm.test.tsx:227` 起：`when shouldUnregister set to true` 一组。
- 文档约定（常识，仓库里没查到）：`shouldUnregister: true` 时只有已注册字段进入提交数据，`defaultValues` 里没注册的不会出现。题面期望（已注册字段的 `values` 要在提交里）与此不冲突，但“未注册字段是否保留”是需要判断的点。

## 【5 边界与隐含要求】
- 只对首次渲染就有的 `values`，还是也包括之后更新的 `values`。
- 与 `keepDefaultValues`、`keepValues`、`keepDirtyValues` 的组合。
- 未渲染或条件渲染的字段，其 `values` 数据在 `shouldUnregister` 下不能被提交。
- 受控字段（Controller / useController）和 field array 的初始值。
- `values` 与 `defaultValues` 同时给的情况。
- 不能破坏 `reset.test.tsx:992` 这类现有断言。
- `isDirty` / `dirtyFields` / `isValid` 的值要和之前保持一致。

## 【6 改动规模】
- 预计 1 到 2 个源文件（`createFormControl.ts` 的 `_reset`，可能还有 `useForm.ts` 的 effect），改动 1 到 3 处。
- 属于局部修补，不用新增结构。风险主要在不破坏既有 reset 行为。
- 需要补一条测试。

## 【7 难点一句话】
根因（`_reset` 在 `shouldUnregister` 下把 `_formValues` 清空，而 `keepFieldsRef` 保留的 field 又不会重新写回值）比较清楚，难点在于既要让 `values` 路径保住值，又不能破坏 `reset()` 在 `shouldUnregister` 下“只留已注册字段”的既有测试和语义。