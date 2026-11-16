# 仓库档案：SSR 下 CSS `v-bind` 与子组件根元素动态 style 合并导致 hydration mismatch

我没法运行 playground，根因没有被代码阅读完全定位。第 7 节列了几个候选，都是推断。

## 【1 题面要点】
- 期望行为：`The inline style bindings in the child component would be resolved properly during SSR to prevent hydration errors.`
- 实际现象：`The style bindings are not being properly merged, triggering a hydration error in SSR`。
- 触发条件：父组件 `<style scoped>` 里用了 `v-bind()`，因此 SSR 往子组件根上注入 CSS 变量。子组件根元素同时有 `:style="{ display }"`。
- 复现：只有 playground 链接（SSR 模式）和 App.vue / ComponentTest.vue 两个文件。
- 没有给期望输出，也没有给修法建议。
- 题面自己的推断是 "which under the hood inlines CSS custom properties on the root of the child component"。
- 版本是 3.4.38。题面没写警告全文，也不知道是哪一项 mismatch。

## 【2 相关代码】
- `packages/compiler-ssr/src/transforms/ssrInjectCssVars.ts:12-68`
  - 只给模板根层节点追加 `v-bind="_cssVars"`。
  - 组件节点也会被追加，所以父组件 SSR 会把 `_cssVars` 当 props 传给 `ComponentTest`。
- `packages/compiler-ssr/src/ssrCodegenTransform.ts:47-59`
  - 生成 `const _cssVars = { style: ... }`。
- `packages/compiler-sfc/src/style/cssVars.ts:17-45`
  - SSR 变量名形如 `--${id}-${escaped}`，生产环境用 hash。
  - SSR 与客户端的转义不同，见 `:40-42` 的 #7823 注释。
- `packages/compiler-ssr/src/transforms/ssrInjectFallthroughAttrs.ts:75-91`
  - 给子组件根元素追加 `v-bind="_attrs"`。
- `packages/compiler-ssr/src/transforms/ssrTransformElement.ts:67-352`
  - `:86-193`：存在动态 v-bind（含 `_attrs`）时走 `ssrRenderAttrs(mergeProps(...))`。
  - `:198-267`：无动态 v-bind 时，把多个 style 合并成一个 `ssrRenderStyle([a, b])`，靠 `mergeCall` 实现（`:408-415`）。
- `packages/runtime-core/src/vnode.ts:869-898`
  - `mergeProps` 的 style 分支是 `normalizeStyle([ret.style, toMerge.style])`。
- `packages/server-renderer/src/helpers/ssrRenderAttrs.ts:87-96`
  - `ssrRenderStyle` 先 `normalizeStyle` 再 `stringifyStyle`。
- `packages/shared/src/normalizeProp.ts:5-61`
  - `normalizeStyle`、`parseStringStyle`、`stringifyStyle`。
  - 字符串和对象混合时，对象分支会原样返回。
- `packages/runtime-core/src/hydration.ts:765-924`
  - `propHasMismatch` 的 style 分支在 `:785-810`。
  - 先构造 `expectedMap`，再调用 `resolveCssVars(instance, vnode, expectedMap)`（`:803-805`）。
  - `resolveCssVars` 在 `:903-924`，靠 `instance.getCssVars` 补期望值，并沿 `instance.parent` 递归。
  - `toStyleMap` 在 `:878-889`，`isMapEqual` 在 `:891`。
  - 调用点在 `:468-476`，第五个参数传的是 `parentComponent`。
- `packages/runtime-dom/src/helpers/useCssVars.ts:19-102`
  - 客户端把变量用 `setProperty` 写到 DOM，不写进 vnode props。
  - `instance.getCssVars` 只在 `__DEV__` 下设置（`:37-39`）。

## 【3 并列与牵连】
- 编译期 `ssrTransformElement` 有两条合并路径：
  - `needMergeProps` 路径（`mergeProps` + `ssrRenderAttrs`）。
  - 静态路径（`mergeCall`）。
  - 如果修的是 style 合并，要两条都看。
- `ssrRenderAttrs`（`ssrRenderAttrs.ts:40-41`）和 `mergeProps`（`vnode.ts:878`）是成对的 style 处理点。
- `ssrTransformComponent.ts` 里也有组件 props 的 style 合并，我没读，需要确认。
- `ssrInjectCssVars` 与 `ssrInjectFallthroughAttrs` 都往同一个根节点追加 `v-bind`，两者的顺序可能影响合并顺序。
- 客户端 `hydration.ts` 的 `resolveCssVars` 只处理根 vnode 和 Fragment 子节点。
- 改 `normalizeStyle`、`stringifyStyle` 或 `mergeProps` 会影响客户端渲染、SSR 和 `runtime-dom` 的 style patch，范围很大。
- 任何改动的 SSR 输出变化都会影响 `compiler-ssr` 的 inline snapshot。

## 【4 现有测试与约定】
- `packages/compiler-ssr/__tests__/ssrInjectCssVars.spec.ts:10-135`
  - 都是 inline snapshot。例如 `:16` 是 `_push(\`<div\${_ssrRenderAttrs(_mergeProps(_attrs, _cssVars))}></div>\`)`。
  - `:54` 是 `_ssrRenderComponent(_component_foo, _cssVars, null, _parent)`。
  - 没有"子组件根带动态 style"的用例。
- `packages/compiler-ssr/__tests__/ssrElement.spec.ts:158-271`
  - 覆盖 `:style`、静态 style 加 `:style`，以及 `style: [{"color":"red"}, _ctx.b]` 的合并。
- `packages/runtime-core/__tests__/hydration.spec.ts:1953-2004`，三个 CSS 变量用例：
  - `:1953`，`should not warn css v-bind`。
  - `:1969`，`css vars should only be added to expected on component root dom`（#10317）。
  - `:1986`，`css vars support fallthrough`（#11188）。子组件根是字符串 style（`'padding: 4px'`），容器 HTML 是 `style="padding: 4px;--foo:red;"`。
  - 断言都是 `expect(\`Hydration style mismatch\`).not.toHaveBeenWarned()`。
  - 现有用例的子组件 style 是字符串，不是对象，也没有 slot。题面是对象 style 加 slot 加 `<script setup>` props。
- 已知约定：hydration 比较 style 时不看顺序（`:786` 注释）。
- 题面期望（不报 mismatch）与现有测试风格不冲突。

## 【5 边界与隐含要求】
- 子组件 style 为对象、字符串、数组三种形态与 `_attrs.style` 的合并。
- 根节点是 Fragment、v-if、Suspense、Transition 时的传递。
- 多层 HOC 嵌套，`resolveCssVars` 沿 `instance.parent` 递归时 `vnode === root` 的判断是否成立。
- slot 内容的 vnode 由哪个组件作 `parentComponent`。
- 值里含冒号的 style（如 `url(http://...)`）会让 `toStyleMap` 的 `split(':')` 出错。
- 生产构建的 hash 变量名，以及 `__DEV__` 下才有 `getCssVars`。
- 变量名转义：SSR 双重转义与客户端 `--${key}` 是否一致。
- 带分号的值，以及 `v-show`。
- 隐藏测试可能落在 `hydration.spec.ts`、`ssrInjectCssVars.spec.ts` 或 `server-renderer` 的 `ssrRender.spec.ts`。

## 【6 改动规模】
- 如果问题在 hydration 比较：改 `hydration.ts` 的一两个函数，1 个文件，局部修补。
- 如果问题在 SSR 合并：涉及 `compiler-ssr` 或 `server-renderer` 的 1 到 2 个文件，几处。
- 多数情况不需要新增结构。
- 需要同步更新 1 到 2 个测试文件的 snapshot 或新增用例。

## 【7 难点一句话】
难在定位：SSR 输出由编译器、`mergeProps` 和 `ssrRenderStyle` 三层共同产生，客户端期望值又靠 `resolveCssVars` 另行推算，题面只给了 playground 链接，没有给出具体是哪一项不一致。

候选根因，都未证实：
- `resolveCssVars` 在某种组件和 slot 结构下的递归或 `vnode === root` 判断失效。
- SSR 与客户端的变量名转义不一致。
- `normalizeStyle` 在字符串与对象混合时返回值与预期不同。