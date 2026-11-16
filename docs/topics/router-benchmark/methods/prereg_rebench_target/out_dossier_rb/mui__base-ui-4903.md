我已经查证了十几处，下面直接给档案。

## 【1 题面要点】
- 要求的行为：Suspense 边界在 `Tabs.Root` 外面，且某个 Panel 的子组件 suspend 时，第一次点击 Tab B 就应渲染 Panel B 的内容，和 v1.4.1 一致。
- 现状：第一次点击不渲染，第二次点击才渲染。
- 题面给了：复现代码（`use(dataPromise)`，Suspense 包在 Root 外）、期望行为、版本范围（只有 v1.5.0 受影响）。
- 修法建议：没有。
- 唯一线索：`Potentially a side effect of https://github.com/mui/base-ui/pull/4704`。CHANGELOG.md:105 写着该 PR 是 "Fire `onValueChange()` for automatic tab selection (#4704)"。
- 题面写 "No new interfaces are introduced."。

## 【2 相关代码】
以下根因是我读代码推出来的，没有运行复现。
- `packages/react/src/tabs/root/TabsRoot.tsx:258-349` 是最可能的根因，一个 `useIsoLayoutEffect`，仅对非受控 Root 生效。
  - 第 287-294 行：`tabMap.size === 0` 且 `didRegisterTabsRef.current` 且 `value !== null` 时，调用 `commitAutomaticValueChange(null, REASONS.missing)`，把 value 设为 null。
  - Suspense 隐藏子树时，React 会销毁隐藏部分的 layout effect。`Tabs.Tab` 因此从 CompositeList 注销，`tabMap` 变空，Root 的 effect 就把 value 重置成 null。
  - 重新显示后，`selectionIsMissing = selectedTabMetadata == null && value !== null`（第 299 行）是 false，所以不会恢复。
  - 结果是选中值丢失，Panel B 的 `open` 为 false，需要再点一次才显示。
- `tabs/root/TabsRoot.tsx:63-79` 的 `getTabElementBySelectedValue`、第 225-243 行的 `selectedTabMetadata` 和 `firstEnabledTabValue`，都依赖 `tabMap`。
- `tabs/root/TabsRoot.tsx:140` 的 `CompositeList` 通过 `onMapChange={setTabMap}` 把 map 同步进来（`TabsList.tsx:140`）。
- `internals/composite/list/CompositeList.tsx:38-111` 管理注册和注销、`mapTick`、`onMapChange`。
- `tabs/panel/TabsPanel.tsx:54-60` 里 `open = value === selectedValue`，`useTransitionStatus(open)` 决定 mounted。第 120-123 行：未 mounted 时返回 null。
- `internals/useTransitionStatus.ts`：`mounted` 初始值是 `useState(open)`。我认为它不是根因，因为渲染期的 setState 在 suspend 重试时会重做。

## 【3 并列与牵连】
- 同样的"空 map 即缺失"逻辑只出现在 Root 这一个 effect 里。`TabsList`/`TabsTab` 只提供注册。
- 受控模式（第 259 行 `isControlled` 直接 return）不受影响。
- 同一个 effect 里还有第 313-340 行的"初始通知"分支和"disabled 回退"分支，改动时要保持它们的语义。
- 其他组件也用 `CompositeList`（比如 toolbar、accordion），但它们没有这套"missing 即重置"的逻辑，所以应该不用同改。
- 改 Root 这个 effect 会影响所有"选中的 tab 被移除"的场景，也就是第 4 节列出的 `onValueChange(null, 'missing')` 行为。

## 【4 现有测试与约定】
- `tabs/root/TabsRoot.test.tsx:937-961`："calls onValueChange with null when the selected tab is removed and no tabs remain"。
  - 断言：`handleChange.mock.calls[0][0]` 为 `null`，`reason` 为 `'missing'`。
  - 断言：之后 `screen.getByRole('tabpanel', { hidden: true })` 带 `hidden` 属性。
- `TabsRoot.test.tsx:907-929` 是"选中的 tab 被移除时触发 missing"，另外 :982 和 :1015 附近有同类用例，后者是受控时不触发。
- `TabsRoot.test.tsx:680-760` 是初始禁用、defaultValue null 等 `initial` 通知相关用例。
- 整个 tabs 目录里没有 Suspense 相关测试（grep 无结果）。
- 约定上，v1.4.1 行为（不因子树暂时隐藏而丢选中值）是题面的期望。
- 与现有测试的关系：Suspense 隐藏和 tab 被真正删除，在 `tabMap` 上看起来一样，所以修复必须区分两者，同时不能破坏上述 `missing` 测试。这是潜在冲突点。

## 【5 边界与隐含要求】
- 区分"被 Suspense 隐藏"和"tab 真的被删除"。可能的办法：
  - 在 effect 里不对空 map 立即重置；
  - 或让 Tab 的注销不触发重置；
  - 或让重置延后，并在 Tab 重新注册时取消。
  我没有核实哪种可行。
- 隐藏期间 `value` 要保持，显示后 `onValueChange` 不应额外触发 `missing`/`initial`。
- `didRegisterTabsRef` 和 `shouldNotifyInitialValueChangeRef` 在隐藏、显示循环中的状态要正确。
- 隐藏期间 Panel A 到 B 的 `tabActivationDirection` 计算依赖 `tabMap`，重新显示后应保持正常。
- 隐藏/显示的重新挂载要兼容 React 18/19、StrictMode（effect 双跑）和 SSR。
- 测试如何模拟 Suspense，是写修复时要想的一点（用 `use()` 配合 Promise 或 lazy）。

## 【6 改动规模】
- 估计 1 个主文件 `TabsRoot.tsx`，改动集中在那一个 layout effect，约 1-3 处，属于局部修补。
- 可能要涉及 `CompositeList.tsx` 或 `TabsTab.tsx`，取决于选哪种修法，但不一定需要。
- 需要新增 1-2 个 Suspense 测试。

## 【7 难点一句话】
难在定位：症状是"Panel 不渲染"，看起来像 `TabsPanel` / `useTransitionStatus` 的问题，实际是 Root 的"tabMap 为空就重置为 null"effect 被 Suspense 隐藏触发。修的时候又要把这种暂时隐藏与真正的 tab 删除区分开，同时不破坏 #4704 的 `missing` 测试。