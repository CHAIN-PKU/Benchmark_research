# 档案：`defineModel` 的 set 转换把值固定成 "a"，在 Firefox 上输入仍然显示

**说明：** 我没有运行复现，也没有打开 playground 链接。下面关于 `set` 提前 return 的分析来自读代码推演，不是实测。

## 【1 题面要点】
- 期望行为：`defineModel` 带 `set` 转换时，输入框里只应保留 "a"，其他输入不应"漏进去"。
- 实际行为：Firefox 上输入框显示了输入的内容。题面猜测是 race condition 或浏览器更新时机不同，"no clue"。
- 复现：只有 playground 链接，链接里的代码我没法读到。步骤是"用 Firefox，输入任意内容"。
- 题面没有给期望输出的代码，也没有给修法建议。
- Interface 一节写着 "No new interfaces are introduced"，所以只改行为，不加 API。

## 【2 相关代码】
- `packages/runtime-core/src/helpers/useModel.ts:20-118`：`useModel` 本体，用 `customRef` 实现。
  - `:45-51`：`watchSyncEffect` 把 prop 同步到 `localValue`，值变化时 `trigger()`。
  - `:59-99`：`set`。`options.set` 转换后得到 `emittedValue`。
  - `:61-66`：提前 return 的条件。
    - 条件是 `!hasChanged(emittedValue, localValue) && !(prevSetValue !== EMPTY_OBJ && hasChanged(value, prevSetValue))`。
    - 也就是 emitted 值等于当前本地值，并且没有"上次 set 过且这次值不同"的情况时，直接 return。
  - `:67-83`：判断父组件是否传了 v-model。没传就本地更新。
  - `:85`：`i.emit`。
  - `:86-96`：#10279 的补丁。当 `value` 与 `emittedValue` 不同、`value` 与 `prevSetValue` 不同、且 `emittedValue` 与 `prevEmittedValue` 相同时，强制 `trigger()`。
  - `:97-98`：记录 `prevSetValue` 和 `prevEmittedValue`。
- `packages/runtime-dom/src/directives/vModel.ts:56-130`：`vModelText`。
  - `:64-67`：input 事件里调用 `el[assignKey](...)`。
  - `:87-119`：`beforeUpdate` 比较 `el.value` 和绑定值，不同才回写。

## 【3 并列与牵连】
- 我推测的根因：`:61-66` 的提前 return 把两件事混在一起了。
  - 首次 `set` 时 `prevSetValue === EMPTY_OBJ`，这时只要 `emittedValue` 等于 `localValue`（输入 "ab"，转换成 "a"，本地已是 "a"），就直接 return。
  - 这样既不 emit，也不 trigger，`prevSetValue` 也没记录。
  - 输入框保持 "ab"，而且之后每次也都是同样的路径。
  - 这个推演还有一处没解释清：它不依赖浏览器，而题面说 Chrome 上正常。可能是 Chrome 上有别的路径补了一次更新，我在代码里没找到，也没验证。
- `:90-96` 的强制 `trigger()` 是 #10279 的补丁，条件很窄，改提前 return 条件时容易互相影响。
- 调用点只有一处：`useModel` 只被 `packages/runtime-core/src/index.ts:66` 导出，`defineModel` 编译产物调用它（`packages/compiler-sfc/src/script/defineModel.ts`）。runtime-core/src 里没有别的调用者。
- `componentEmits.ts:33` 只用了 `getModelModifiers`，不受影响。
- 没有并列的实现，例如 vapor 或 `runtime-vapor`。我只在 `packages` 下搜了 `useModel`，结果里没有这类文件。
- 改动会影响所有 `defineModel` 加 `get/set` 的组件，包括 `.number`、`.trim` 之类修饰符转换。

## 【4 现有测试与约定】
- `packages/runtime-core/__tests__/helpers/useModel.spec.ts:531-`，#10279 用例 "force local update when setter formats value to the same value"。
  - setter 对 `number` 修饰符做 `val.replace(/\D+/g, '')`。
  - `:589` 初始断言 `expect(serializeInner(root)).toBe('<input value=1></input>')`。
  - `:594` 模拟 `input.props.onInput((input.props.value = '2'))`，后续断言我只读到 `:594` 为止，没看。
  - 该用例用 v-model 的模拟方式：在 `onVnodeBeforeUpdate` 里写 `vnode.el.props.value = childMsg.value`。
  - 它覆盖的是"先改成别的值再被转换回去"，没有覆盖"从未改过值就转换回原值"的首次 `set`。
- `:706-751`，#11541 "custom setter"：`changeChildMsg(true)` 之后 `msg.value` 为 `true`，再 `changeChildMsg(true)` 之后为 `null`。改提前 return 时要保证它仍然通过。
- `:525-529` 附近的用例断言 `expect(msg.value).toBe('UGHH')`，是大写转换，同样要保留。
- 我没找到文档里规定的行为，也没看到与题面冲突的约定。

## 【5 边界与隐含要求】
- 首次 `set`，也就是 `prevSetValue` 为 `EMPTY_OBJ` 的情况，要能触发本地刷新。
- 父组件传了 v-model 与没传时，行为都要对。没传时 `:81-82` 已经本地更新。
- `value` 与 `emittedValue` 不同、`emittedValue` 与 `localValue` 相同时，需要 `trigger()`，让输入框回写。
- 不能引入重复 emit，或打破 #11541 里 `null` 的语义。
- 要覆盖 `prevSetValue`、`prevEmittedValue` 的更新时机，避免提前 return 后状态没记录。
- `vModelText.beforeUpdate` 的 `:101` 对比，必须能拿到触发后的更新。如果没有重新渲染，它就不会回写。

## 【6 改动规模】
- 可能只改 `useModel.ts` 一个文件，改 `:61-66` 提前 return 的条件，或调整 `:90-96` 的强制 trigger。
- 隐藏测试大概率在 `useModel.spec.ts`，新增一个用例，属于局部修补，不涉及新结构。

## 【7 难点一句话】
难在隐藏测试没法在 Firefox 里跑，只能在 runtime-core 的模拟元素上重现。所以要先判断清楚哪个条件分支造成了"没触发刷新"，再改条件，同时不破坏 #10279 和 #11541 已有的行为。