# 仓库档案：Floating terminal 关闭最后一个 tab 后自动重建

## 【1 题面要点】
- 期望行为：点 X 关闭最后一个 tab 时面板应关闭。现状是面板停留并自动新建一个 tab。
- 题面给了复现步骤（热键打开、点 X），也给了期望与实际。
- 根因题面已点明：X 按钮的 `closeTab` 会触发 `FloatingTerminalPanel.tsx` 第 97–103 行的 effect。该 effect 在 `open && tabs.length===0` 时自动建 tab。
- 题面没有给具体修法。隐含的修法是：只在面板从关到开的转换时建 tab。
- 评测契约（关键句）：
  - "Bootstrap a terminal tab only when the panel transitions open."
  - "An explicit close action that removes the last tab closes the panel; a PTY exit removes its tab but must neither close the panel nor create a replacement tab."
  - "Bulk close operations must read the current store state rather than a stale render-time tab list, and `closeToRight` must follow the reconciled visible tab-bar order rather than raw backing-array order."
- 题面说"No new interfaces"。

## 【2 相关代码】
所有改动点基本都在 `src/renderer/src/components/floating-terminal/FloatingTerminalPanel.tsx`。
- 第 97–103 行：自动建 tab 的 effect。依赖是 `[createTab, open, setActiveTabForWorktree, tabs.length]`，所以 tabs 清零时也会触发。
- 第 169–174 行：`closeFloatingTab` 只调用 `closeTab(tabId)`，是 X 按钮的 `onClose`（第 307 行）。这里要加"关掉最后一个就 `onOpenChange(false)`"的逻辑。
- 第 176–185 行：`closeOthers` 遍历渲染期闭包里的 `tabs`，是旧状态。
- 第 187–198 行：`closeToRight` 用 `tabs.findIndex` 和 `tabs.slice` 取右侧 tab，既是旧状态，也是后备数组顺序，不是 tab 栏可见顺序。
- 第 339–347 行：`TerminalPane` 的 `onPtyExit={() => closeTab(tab.id)}` 和 `onCloseTab={() => closeTab(tab.id)}`。
  - `onPtyExit` 直接走 store 的 `closeTab`，没有经过 `closeFloatingTab`，题面要求 PTY 退出不关面板。
  - `onCloseTab` 是用户显式关闭（或 pane 生命周期里关最后一个 pane）的路径，可能也要走显式关闭逻辑。这一点需要核对。
- `src/renderer/src/store/slices/terminals.ts:499` 起的 `closeTab`：同步清理 tabs、`activeTabIdByWorktree`、`tabBarOrderByWorktree`（第 558 行起）。
- `src/renderer/src/components/tab-bar/reconcile-order.ts:6`：`reconcileTabOrder(stored, terminalIds, editorIds, browserIds)`。它负责去重、剔除无效 id、把新 id 追加到末尾。`TabBar.tsx:201-232` 用它得到可见顺序。
- `src/renderer/src/App.tsx:221、1451`：`open` 状态在 App 里，面板通过 `onOpenChange` 控制。

## 【3 并列与牵连】
- `terminal-tab-actions.ts:89-117` 的 `closeTerminalTabsToRight` 是现成参考实现。它在函数内用 `useAppStore.getState()`，并调用 `reconcileTabOrder(state.tabBarOrderByWorktree[wt], terminalIds, editorIds)` 得到可见顺序。
- `terminal-tab-actions.ts:75-87` 的 `closeOtherTerminalTabs` 也在函数内读 `getState()`。但它依赖 `activeWorktreeId`，不适合浮动面板，浮动面板用的是固定 `FLOATING_TERMINAL_WORKTREE_ID`。
- 并列的 `closeOthers` 和 `closeToRight` 都要改。它们最后也可能把 tab 清空，需要决定是否同样关面板。`closeOthers` 保留当前 tab，所以不会清空。`closeToRight` 保留 tabId 及其左侧，也不会清空。
- 其他自动建 tab 或操作浮动 worktree 的地方：
  - `FloatingTerminalWindowControls.tsx:57-81` 的 `launchDefaultAgent` 手动新建 tab。
  - `FloatingTerminalPanel.tsx:151-167` 的 `createFloatingTab`。
  - 两处都已经用 `getState()` 读新状态，可作为写法参考，改动不必涉及。
- 面板始终挂载，只用 `open` 切换 `visibility`，所以 effect 需要用 ref 记住上一次的 `open`，才能识别关到开的转换。
- 其他 `onPtyExit` 的使用方（`Terminal.tsx`、`FeatureSetupInlineTerminal.tsx`）与浮动面板无关。

## 【4 现有测试与约定】
- `floating-terminal` 目录下只有 `floating-terminal-panel-bounds.test.ts`。面板组件本身没有测试。
- `reconcile-order.test.ts:6-33` 断言 `reconcileTabOrder` 的行为，例如 `['gone','t1']` 只剩 `['t1']`，存储顺序之外的追加到末尾。
- `TabBar.context-menu.test.ts:236-253` 断言 `onCloseToRight` 收到的是 `unifiedTabId`。这个测试针对 TabBar，浮动面板的断言需要新写。
- 存量测试里没有与题面冲突的断言。
- 隐藏测试大概率要渲染或模拟面板，难度比普通纯函数测试高。可能的形式有两种：
  - 把逻辑抽成纯函数后测试。契约说"没有新接口"，这种可能性较小。
  - 用 react 测试渲染器或 mock store 调用面板里的回调。仓库里有 TabBar 的 mock 渲染测试（`TabBar.context-menu.test.ts`），可作为风格参考。
- 约定：仓库注释风格是 `// Why: ...`，改动处最好加上。

## 【5 边界与隐含要求】
- "最后一个 tab"必须在 `closeTab` 之后用 `getState()` 重新读取判断，不能用渲染期的 `tabs.length`。
- PTY 退出的 tab 被移除后，面板不能关，也不能重建 tab。因此自动建 tab 的 effect 不能再依赖 `tabs.length`。同时要保证面板打开时 tabs 为 0 的一次性引导仍然成立。
- 面板在"已关闭"状态下 tabs 也可能为 0，重新打开时必须建 tab。例如热键关闭、PTY 全退出后再打开。
- 面板关闭但 tab 仍在时再打开，不应再建 tab。
- 严格模式下 effect 可能执行两次，要避免重复建 tab。
- `closeToRight` 要基于 `reconcileTabOrder(store 里的 tabBarOrder, 当前 tab ids, [], [])` 的可见顺序，而不是 `tabs` 数组顺序。
- `closeOthers` 和 `closeToRight` 的 tabId 如果已不在当前 store 里，要静默返回。
- 批量关闭时中间状态不应触发关闭面板。
- `onCloseTab` 应该走显式关闭语义还是 PTY 退出语义，需要看 `use-terminal-pane-lifecycle.ts:953` 附近。该处在最后一个 pane 关闭时 `closeTab(tabId)`，属于用户显式关闭，所以这条路径大概率要关面板。
- 浮动 worktree 没有编辑器和浏览器 tab，所以 `reconcileTabOrder` 的后两个参数传空数组即可。

## 【6 改动规模】
- 基本只改 1 个文件：`FloatingTerminalPanel.tsx`，约 4–6 处。
  - effect 改为"打开时转换触发"（用 ref）。
  - `closeFloatingTab` 加"空则关面板"。
  - `closeOthers` 和 `closeToRight` 改读 `getState()`，后者按 reconcile 顺序。
  - `TerminalPane` 的 `onCloseTab` 是否改走 `closeFloatingTab`。
- 属于局部修补，不新增结构。若要让逻辑可测，可能需要抽出小函数，但契约说不新增接口。

## 【7 难点一句话】
改动本身不大，难点有三处：
- 把"开启时引导"和"PTY 退出不重建也不关面板、显式关闭才关面板"这几条语义分清楚。
- `closeToRight` 要按可见的 tab 栏顺序，而不是数组顺序。
- 面板组件没有现成测试，隐藏测试的形式只能靠猜。