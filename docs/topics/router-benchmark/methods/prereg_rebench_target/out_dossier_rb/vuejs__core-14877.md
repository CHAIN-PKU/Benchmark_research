# 仓库档案：Teleport + Suspense 卸载 pending teleport 时崩溃

## 【1 题面要点】
- 期望行为：Suspense 内的 `<Teleport>` 在挂载执行前就被卸载时，Vue 应干净移除，不抛错。题面称 3.5.30 正常。
- 实际行为：3.5.31 到 3.5.34 抛 `TypeError: Cannot read properties of null (reading 'type')`。调用栈是 `unmountComponent` ← `unmount` ← `Teleport.remove` ← `unmount` ← `unmountChildren` ← … ← Suspense `resolve`。
- 复现：外部仓库有浏览器点击和 3 个 vitest。题面正文没有给出内联的最小代码。
- 没有给修法建议。只给了回归链路：#8619 引入 `pendingMounts`，#14642 加了 `pendingMount` 检查，#14702 只在 `moveTeleport` 里加了 `pendingMounts.has(vnode)` 守卫。
- 题面明确点出：`TeleportImpl.remove` 这条路径没人动过，而且 #14642 只拦了元素子节点的 DOM 移除，没拦组件子节点的 `unmountComponent(null, …)`。
- 触发条件是 teleport 的子节点是组件，并且 `vnode.component === null`。

## 【2 相关代码】
- `packages/runtime-core/src/components/Teleport.ts:317-364`，`TeleportImpl.remove`。
  - 338-343 行：发现 `pendingMounts.get(vnode)` 后，把 job 标记为 DISPOSED，删除记录，并设 `shouldRemove = false`。
  - 352-363 行：无条件遍历 `children` 调 `unmount(child, …, shouldRemove, …)`。这里就是崩溃点。pending 状态下子 vnode 从未 mount，`child.component` 为 null。
- `packages/runtime-core/src/renderer.ts:2172-2173`：`unmount` 遇到 `ShapeFlags.COMPONENT` 就执行 `unmountComponent(vnode.component!, …)`。非空断言在这里失效。
- `renderer.ts:2312-2321`：`unmountComponent` 一上来就解构 `instance.type.__hmrId`，instance 为 null 时在这里抛错。
- `Teleport.ts:160-176`：`queuePendingMount`，经 `queuePostRenderEffect(mountJob, parentSuspense)` 入队。
- `Teleport.ts:189-195`：`isTeleportDeferred(props)` 或 `parentSuspense.pendingBranch` 存在时走 pending 路径，并 return。
- `Teleport.ts:203-216`：patch 更新时，如果 `n1` 还在 pending 就废弃旧 job，并对 n2 重新排队。
- `Teleport.ts:397`：`moveTeleport` 里 #14701 加的 `!pendingMounts.has(vnode)` 守卫。可作参考实现。

## 【3 并列与牵连】
- 最直接的并列实现是 `moveTeleport`。它已经处理了 pending，`remove` 是对称的缺口。
- `Suspense.ts` 的 `unmount`/`resolve` 在 595 行 `unmount(activeBranch, …, true)`，以及 295 行 `unmount(pendingBranch, …)`。这些是触发入口，不需要改，但决定了复现路径。
- 还没确认的相关路径：
  - `hydrateTeleport`（`Teleport.ts` 约 421 行起）。水合时是否会产生 pending，没有细看。
  - 题面没提 KeepAlive，但 `renderer.ts:2156` 的 `deactivate` 路径同样依赖 `vnode.component`。
  - `Teleport.ts:210-216` 的更新路径已经处理了 pending。
- 改 `remove` 会影响所有 teleport 卸载。守卫只在 pending 分支生效，所以非 pending 路径不变。
- `Teleport.ts:345-348`：pending 时 `target` 在 mount 前未赋值，当前不会误删 targetStart/targetAnchor。pending 状态下 `vnode.target` 为 null。这一点我没有再核对 `targetStart`。

## 【4 现有测试与约定】
- `packages/runtime-core/__tests__/components/Suspense.spec.ts` 里没有断言 `pendingMount` 的字面量。
- 已有同类测试：
  - 约 2492-2521 行：Suspense pending 期间 `showTeleport.value = false`。断言 `serializeInner(root)` 为 `<div>fallback</div>`，`serializeInner(target)` 为 `` ``。子节点是 `h('div', 'teleported')`，是元素，不是组件。
  - 2523-2574 行：`should not process discarded disabled teleport update after suspense is resolved`，同样用元素子节点。
  - 2576-2612 行：`// #14701` 的测试，teleport 带组件子节点，但走的是 move，不是 unmount。
- 缺口：现有测试都没有覆盖"pending teleport + 组件子节点 + 卸载"。隐藏测试大概率就是这个场景，可能还会加断言 target 里没有残留、teleport 的 `mounted`/`unmounted` 钩子没有触发。
- 约定：断言风格是 `nodeOps` + `serializeInner`。修复里要沿用 DISPOSED 标志加 `pendingMounts.delete` 的机制。
- 与题面期望没有冲突。

## 【5 边界与隐含要求】
- 子节点是组件、Fragment 里嵌组件、多个子节点的混合情况。
- 子节点中的组件可能是异步组件。
- 未 mount 的组件子节点不应该触发 `beforeUnmount`/`unmounted` 钩子，因为它们从未 mounted。
- 判断条件应该是 pending 状态，不能简单吞掉 null component。否则会掩盖真正的 bug。
- `doRemove` 为 true 时，仍要 `hostRemove(anchor)`，也就是 `el`/`anchor` 占位注释（见 351 行）。
- disabled 的 teleport 在 pending 期间：mount 时 children 会放进主容器，但 pending 期间没放，同样不能卸载子节点。
- Suspense 已解析后 pending 的 job 因为 DISPOSED 不会再执行。需确认 `queuePostRenderEffect` 到 Suspense 的 effects 缓冲里的 job 在 flush 时会被跳过。
- 子 vnode 上的指令 `dirs`、`ref`（`setRef`）在 `unmount` 开头会被调用，对未 mount 的 vnode 也会跑。这里可能有额外问题，我没验证。

## 【6 改动规模】
- 主要在 `Teleport.ts` 的 `remove` 里加分支，局部修补，约 1 个文件、1 到 2 处。
- 可能的替代修法是在 `renderer.ts:2173` 加 null 判断，也是 1 处。
- 另外要加测试（`Suspense.spec.ts` 或 `Teleport.spec.ts`）。
- 不需要新增结构，不贯穿多层。

## 【7 难点一句话】
改动本身很小，难点是判断该在哪一层挡住（`Teleport.remove` 里跳过未挂载的子节点，还是 `unmount` 里容忍 null component），还要保证 `ref`/指令/钩子对未挂载 vnode 的副作用不出问题，而且别破坏 #14642 和 #14702 已有的行为。

**说明**：我只做了约 10 次搜索和阅读，`hydrateTeleport`、KeepAlive 交互、`setRef` 和 `dirs` 对未挂载 vnode 的影响没有逐行核实，上面凡标注"没验证"的地方都属于推测。