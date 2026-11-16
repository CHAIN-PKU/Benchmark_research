**档案：Pi-only 安装流程中「Back」跳转错误**

**【1 题面要点】**
- 要求：只选 `Pi` 并继续后，在下一步（DependencyTree 依赖/计划页）选 `Back`，应回到上一个相关步骤，即 Agents 选择页。
- 现状：回到了 Preset 页。题面描述的是它后面接着出现的 TDD、multi-agent、沟通风格等配置页。
- 题面没有复现代码，也没有给修法。
- 唯一的期望句是 "the installer should return to the previous relevant step in the Pi-only installation flow, likely the installation target selection screen"。
- 题面写 "No new interfaces are introduced"。

**【2 相关代码】**（均在 `internal/tui/`）
- `model.go:1483-1498`：Agents 页的 Enter 处理。Pi-only 时设 `Components=piOnlyComponents()`，调用 `buildDependencyPlan()`，然后直接 `setScreen(ScreenDependencyTree)`，跳过 Persona 和 Preset。这是前进路径。
- `model.go:2321 goBack()`：Esc 的统一返回函数。
  - `ScreenDependencyTree` 非 custom 分支（2436-2450）只处理 OpenCodePlugins、StrictTDD、ClaudeModelPicker。
  - 其余情况落到 2584 的 `PreviousScreen`，即 `router.go:20` 的 `ScreenDependencyTree: Backward: ScreenPreset`。这就是 bug 的根源。
- `model.go:1758-1823`：DependencyTree 页 Enter 的非 custom 分支。`Cursor==0` 前进到 Review；否则是 Back，依次判断 StrictTDD、SDDMode、Claude 选择页，最后默认 `setScreen(ScreenPreset)`（1822）。这是第二处同样的错误。
- `model.go:3134 isPiOnlyAgents`：判断函数，已存在。
- `router.go:8-51 linearRoutes`：静态路由表，无法表达 Pi-only 这种动态分支。

**【3 并列与牵连】**
- Back 有两条并列路径，注释写着 "keep in sync"：Esc 走 `goBack()`，选中 "Back" 项走 `model.go:1799-1823`。两处都要改，题面说的「选 Back」是后者。
- `ScreenReview` 的 Back（1889-1891）和 `goBack` 的 Review 分支（2545-2576，非 custom 走 linearRoutes）都回到 DependencyTree。这是对的，不用改。
- Pi-only 是否也要处理 Persona 页的反向？Persona 页 Back 回 Agents（1506），本来就对，且 Pi-only 到不了该页。
- `internal/cli/validate.go:230` 另有一份 `isPiOnlyAgents`/`piOnlyComponents` 重复实现。那是 CLI 路径，与本题无关。
- 改动只影响 TUI 导航，不涉及安装逻辑。

**【4 现有测试与约定】**
- `model_test.go:238 TestPiOnlyAgentContinueSkipsPromptsAndIncludesEngram`：断言 `state.Screen == ScreenDependencyTree`，Components 等于 `[Engram]`，`DependencyPlan.Agents` 为 `[pi]`。只测前进，不测返回。
- `model_test.go:283 TestPiCombinedWithOtherAgentKeepsGenericFlow`：Pi 加 OpenCode 时 `Screen == ScreenPersona`。混合选择的流程必须保持不变。
- `model_test.go:263`：`NewModel` 检测到 Pi 时默认 `[Engram]`。
- `agent_builder_nav_test.go:332` 等测试用 `m.Update(KeyMsg)` 配合断言 `Screen`，这是写隐藏测试的参考方式。
- 约定：代码注释要求两处 Back 逻辑 "keep in sync"。
- 没有发现现有测试断言「DependencyTree 返回 Preset」会与题面冲突。我没有逐个核对所有测试。

**【5 边界与隐含要求】**
- Pi 与其他 agent 混选时，Back 仍应回 Preset，或原有的 StrictTDD/Claude 页。
- 判断条件应是 Pi-only 且非 custom。Pi-only 的 `Preset` 是默认的 FullGentleman，所以走 2436 的非 custom 分支。
- Pi-only 的 Components 只有 Engram，`shouldShowStrictTDDScreen` 等判断本来就为 false，所以判断顺序上新分支放在这些检查之后或之前都可以。
- 回到 Agents 页后，已选的 Pi 应保持选中，光标位置会被 `setScreen` 重置为 0。
- 回到 Agents 后再次前进应仍能正常进入 DependencyTree。
- Esc 和选 "Back" 项两种方式都要测到。
- DependencyTree 页的 Back 项下标：Pi-only 页面是否仍是 `Cursor>0` 为 Back，需要看渲染（`screens/dependency_tree.go:90`）。

**【6 改动规模】**
- 约 1 个文件（`model.go`），2 处局部补丁：`goBack` 和 Enter-Back 分支，各加一个 Pi-only 判断并回到 `ScreenAgents`。
- 可能顺带加测试。
- 不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
难点不在改法，而在发现 Back 有 Esc 和菜单项两条独立路径、都要改，并且不能影响 Pi 混选的流程。整体改动量小。