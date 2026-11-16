# 仓库档案:programmatic 打开后关闭时,焦点回到了 triggerId 对应的触发器

说明:下面的检索覆盖了 FloatingFocusManager、dialog 和 popover 的 store、popupStoreUtils、各组件测试。没有查看 alert-dialog 的 Popup 源码、PopoverPopup 的实现、站点 docs demo、`useFloatingRootContext.ts` 的细节,也没有运行任何测试。

## 【1 题面要点】
- 要求的行为:在"Controlled mode with multiple triggers"示例里,用 "Open programmatically" 按钮打开 Alert Dialog、Dialog 或 Popover,关闭后焦点应回到这个按钮。
  - 现状是焦点回到了别的触发器(例如 "Delete")。
  - 题面期望:"Keyboard focus should move back to the originating control (if available)"。
  - 备用要求:"If the control is no longer available, focus should move next to that originating control's position in the DOM."
- 复现步骤:键盘聚焦 "open programmatically",按 Enter 打开,按 Esc 或点关闭,焦点落在 "Delete"。
- 没有给出期望输出代码,也没有给出具体修法。
  - 唯一的建议是 "Recommend keeping track of focus and returning it to the originating control."
  - 接口部分写明"No new interfaces are introduced"。
- 题面没有说明这个按钮是否有 `triggerId`,也没说 `Root` 是否受控。

## 【2 相关代码】
- `packages/react/src/floating-ui-react/components/FloatingFocusManager.tsx:727-858`:负责"跟踪返回焦点目标并在卸载或关闭时恢复"的 layout effect,最可能是主改动点。
  - `getReturnElement()`(780-807):`returnFocus` 为 true 或 null 时,先用 `domReference?.isConnected ? domReference`,否则用 `getPreviouslyFocusedElement()`。
  - 清理函数(809-847):`queueMicrotask` 里对 `tabbableReturnElement` 调用 `.focus({preventScroll:true})`。
  - `domReference` 就是当前激活触发器。programmatic 打开时 `triggerId` 指向 trigger-2,于是焦点优先回到 trigger-2,不回"打开按钮"。
  - 73-93 行有模块级的 `previouslyFocusedElements` 列表(`addPreviouslyFocusedElement`、`getPreviouslyFocusedElement`),只在 domReference 断开时才用。
  - 733-735 行在 effect 运行时记录 `activeElement(doc)`,但此时可能已经不是真正的"打开者",因为打开者可能已失焦或弹窗已经抢了焦点。
- `packages/react/src/dialog/popup/DialogPopup.tsx:120-129`:`<FloatingFocusManager returnFocus={finalFocus} restoreFocus="popup" ...>`。`PopoverPopup.tsx` 和 `AlertDialog` 的 Popup 预计同构,我没有打开核对。
- `packages/react/src/utils/popups/popupStoreUtils.ts:119-132`(`setOpenTriggerState`)和 `152-190`(`useTriggerDataForwarding`)设置并同步 `activeTriggerId` 和 `activeTriggerElement`。
- `popupStoreUtils.ts:208-242`(`useImplicitActiveTrigger`)在只有一个 trigger 时隐式设为激活。
- `packages/react/src/utils/popups/store.ts:106-122`(`createPopupFloatingRootContext`)创建 `FloatingRootStore`,`referenceElement: null`。`domReferenceElement` 由 `floating-ui-react/hooks/useFloatingRootContext.ts:64` 从 `elements.reference` 同步。
- `packages/react/src/dialog/store/DialogStore.ts:90-93`:关闭时若没有 trigger,会把 `eventDetails.trigger` 补成 `activeTriggerElement`。
- `packages/react/src/dialog/store/DialogHandle.ts:28-42`:imperative 的 `open(triggerId)` 路径。
- `packages/react/src/popover/store/PopoverStore.ts:147` 也引用 `activeTriggerElement`。

## 【3 并列与牵连】
- Dialog、AlertDialog、Popover 三者题面都点名。它们共用 `FloatingFocusManager`,所以修在共享层最省事。
- Drawer(`drawer/popup/DrawerPopup.tsx`)、Menu、Combobox、Select 也使用 `returnFocus`,共 8 个文件。改 `getReturnElement` 的默认逻辑会波及它们,尤其是 Menu 和 Select,它们依赖"回到 trigger"。
- Tooltip 和 PreviewCard 同样用 `createPopupFloatingRootContext`,但不做焦点管理。
- 如果在 store 层(记录"打开时的焦点元素")修,Dialog、Popover、AlertDialog 的 store 各一份,可能要在 `popupStoreUtils` 里共用。
- 与 `restoreFocus="popup"`(482-500 行)可能有交互。
- 还要考虑 `finalFocus` 显式值、`outsidePress` 的 `preventReturnFocusRef`、嵌套弹窗。

## 【4 现有测试与约定】
- `dialog/popup/DialogPopup.test.tsx:416-441`:"should focus the trigger by default when closed",断言 `expect(trigger).toHaveFocus()`。
  - 455-480 行是 `finalFocus={inputRef}` 的测试,482 行起是函数形式的测试。
  - 这些都只覆盖单 trigger,不覆盖 programmatic。
- `dialog/root/DialogRoot.detached-triggers.test.tsx:179-225`:"sets the payload when opening programmatically with a controlled triggerId",只断言 payload,不断言焦点。
- `popover/root/PopoverRoot.detached-triggers.test.tsx:165` 和 `:502`:"should allow controlling the popover state programmatically"。
- `alert-dialog/root/AlertDialogRoot.test.tsx:387`:multiple triggers 的测试,标注 `skipIf(isJSDOM)`,所以这类测试只在浏览器里跑。
- 其他有 finalFocus 测试的文件:`popover/popup/PopoverPopup.test.tsx`、`menu/popup/MenuPopup.test.tsx`、`select/popup/SelectPopup.test.tsx`。
- 约定:默认回到触发器(这是已有测试锁定的行为)。外部规范是 WCAG 2.4.3 和 WAI-ARIA 对话框模式(回到调用元素)。
- 与题面不冲突。但"默认回 trigger"和"回到 opener"在 programmatic 场景要区分,需要决定优先级:
  - 实际点击过的 trigger 要回到该 trigger;
  - programmatic 要回到打开前的焦点元素。

## 【5 边界与隐含要求】
- 如何判断"这次打开是 trigger 点击还是 programmatic":点击 trigger 时焦点本身就在 trigger 上,所以"打开时的 activeElement"在两种情况下都可能是正确的返回目标。
- 打开时的 `activeElement` 若是 `body`,需要回退到 trigger 或 domReference。
- 鼠标点击在 Safari 上不聚焦按钮,所以"记录 activeElement"在 Safari 可能拿到 body。
- 返回目标被移除后要用"DOM 里的下一个位置"做备用。题面明确要求,现有代码只回退到 `getPreviouslyFocusedElement`,没有位置回退。
- `finalFocus` 显式传入时优先。
- 切换激活 trigger(多个 trigger 之间转移)时,要保证返回目标不是旧的。
- 受控 `open` 与 `triggerId` 变化的时序:state 在 effect 里才同步,effect 在 733 行记录的 `activeElement` 可能已被弹窗的 initialFocus 抢走。这是最需要核实的点。
- `preventReturnFocusRef` 的 outsidePress 逻辑、React Strict Mode 的双重渲染(530 行注释)、hover 打开的 Popover。
- 需要同时覆盖键盘 Esc 和点击 Close 两种关闭方式。

## 【6 改动规模】
- 如果修在 `FloatingFocusManager`:1 个主文件,几处局部改动(记录打开时的焦点元素、修改 `getReturnElement` 的优先级)。
- 若还要补"位置回退",则需要新增逻辑(记录兄弟或父节点),规模略大。
- 可能再改 1 至 3 个 Popup 或 store 文件。
- 需要加测试(dialog、alert-dialog、popover 的浏览器测试)。
- 总体偏局部修补,不贯穿多层。但共享层改动的回归面大(Menu、Select、Combobox、Drawer)。

## 【7 难点一句话】
难在设计"返回目标"的判定:要把 programmatic 打开的"打开者"和普通 trigger 点击区分开,又不能破坏 Menu、Select 等已有的"回到 trigger"约定。另外,打开时刻拿到的 `activeElement` 在受控状态同步的时序下不一定可靠。