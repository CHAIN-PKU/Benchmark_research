## 仓库档案：kueue MultiKueue「worker 断连后 admitted workload 过早重新排队」

所有行号都来自本快照，以下是查证结果（未使用对上游修法的记忆）。

### 【1 题面要点】
- 要求的行为：worker 临时断连时，已 admitted 的 workload 保持 Ready，只在配置的 worker-loss 超时（`WorkerLostTimeout`）之后才重试。用同样配置重连后要恢复处理，且不影响其他已连接的 worker。
- 题面没有给复现步骤、期望输出或修法建议。
- 关键句：“No new interfaces are introduced.”，即不新增 API 或配置项。

### 【2 相关代码】
都在 `pkg/controller/admissionchecks/multikueue/`：
- `workload.go:328` `reconcileGroup`：核心状态机。
  - `:459-514` 第 6 步先找有 Admitted 条件的 reserving remote。
  - `:503` 找到时返回 `RequeueAfter: w.workerLostTimeout`。
  - `:504-513` 没找到且 `acs.State==Ready` 时，计算 `remaining := workerLostTimeout - time.Since(acs.LastTransitionTime)`。`remaining>0` 就继续等待。否则调用 `updateACS(..., CheckStateRetry, "Reserving remote lost")`。
- `workload.go:979` `syncReservingRemoteState`：只在 AC 状态变化时（`needsACUpdate`，`:983`）写 `acs.LastTransitionTime`，注释写着“used to detect the lost worker state”（`:998`）。
- `workload.go:114` 的 `SetAdmissionCheckState`（`pkg/workload/admissionchecks.go:115-135`）只在 State 改变时才更新 `LastTransitionTime`。
- `workload.go:253` `remoteClientsForAC`：跳过 `connecting` 为 true 的 client（`:262`）。全部不可用时返回 `admissioncheck.ErrNoActiveClusters`（`:267`）。
- `workload.go:298` `readGroup`：把上面的错误包装后返回，`Reconcile`（`:225-228`）因此直接报错，不进入 `reconcileGroup`。
- `multikueuecluster.go:235` `setConfig`、`:385` watch 结束时 `connecting.Swap(true)`、`:294` 重连成功后置 false、`:678` `clustersReconciler.Reconcile`、`:625` `stopAndRemoveCluster`（配置加载失败时删除 client）。
- `multikueuecluster.go:511` `runGC`、`clusterqueue.go:192` 也使用 `connecting` 标志。

### 【3 并列与牵连】
- 疑点 A（“过早”的主因）：超时是从 `acs.LastTransitionTime` 起算。这个时间是 AC 变 Ready 的时刻，不是断连的时刻。健康运行超过 `workerLostTimeout`（默认 5 分钟，`controllers.go:36`）后一断连，`remaining<=0`，立即 Retry。
- 疑点 B：只有一个 worker 且断连时，`remoteClientsForAC` 返回 `ErrNoActiveClusters`。`reconcileGroup` 不会被执行，workload 既不进入超时逻辑，也不会被重新排队。这可能被报错重试掩盖，也可能让 workload 永远卡住。
- 疑点 C：多 worker 时，断连的 worker 被排除在 `remotes` 之外，所以 `bestMatchByCondition` 找不到 reserving remote。这正是第 504 行分支的触发条件。
- 第 6 步“删除未选中 worker 的 workload”（`:463-471`）、第 2 步和第 3 步都用 `group.remotes` / `group.remoteClients`，断连集群缺席会影响这些路径。
- 第 4 步（`:374-409`）的“worker 上被驱逐 → Retry”是并列的状态迁移，改动时需保持一致。
- `workloadToOpenPreemptionGate`、`nominateAndSynchronizeWorkers` 也依赖 group.remotes，但与本题关系较弱。
- 其他调用点：`clusterqueue.go:192` 对 `connecting` 的使用，以及 `runGC` 的跳过逻辑，如果改变连接状态语义需要核对。
- “重连后同配置恢复”：`setConfig` 在 `!configChanged && !connecting` 时直接返回（`:238`）。需要确认重连后 workload 能再次被 reconcile。`startWatcher` 会通过 `queueWorkloadEvent` 触发事件。

### 【4 现有测试与约定】
- `workload_test.go:790` “Ready if the remote WorkerLostTimeout is not exceeded”：LastTransitionTime 为 now−timeout/2，期望保持 Ready。
- `workload_test.go:819` “set to Retry if the WorkerLostTimeout is exceeded”：LastTransitionTime 为 now−1.5×timeout，期望 `State: Retry, Message: "Reserving remote lost"`。
  - 这两个测试把“LastTransitionTime 作为计时起点”固化了。如果修法改了计时语义，这两个用例的前置状态可能需要同步调整，也可能与隐藏测试冲突。
- `workload_test.go:269` “reconnecting clients are skipped”：`worker2Reconnecting` 为 true 时期望 `wantError: nil`，只有一个 worker 被跳过。
- `workload_test.go:1117` 另有一处期望消息为 "Reserving remote lost"。
- `workload_test.go:1566, 1597` 通过 `connecting.Store(false)` 控制 worker 连接状态；`:1606` 用 `newWlReconciler(..., defaultWorkerLostTimeout, ...)` 和 `WithClock` 注入假时钟。
- `multikueuecluster_test.go:752` `TestReconnectBackoff`、`:99` `setReconnectState`。
- `pkg/util/admissioncheck/admissioncheck_test.go:301` 断言 `ErrNoActiveClusters`。
- 集成测试：`test/integration/multikueue/suite_test.go:68` 设 `testingWorkerLostTimeout = 3s`，`setup_test.go:1321/1358` 也有使用。
- e2e：`test/e2e/multikueue/sequential/e2e_test.go:300-364` 通过 docker 改 apiserver 绑定地址模拟断连，只断言集群状态。
- 规范来源：`keps/693-multikueue/README.md`（提到 WorkerLostTimeout 两次）、`apis/config/v1beta2/configuration_types.go`。我没有读 KEP 原文，具体表述未核实。
- 与题面冲突：现有测试断言 Ready 保持是以 LastTransitionTime 为基准。题面强调“断连后再等超时”，两者对起点的定义不同，需要选一个“断连时间”的来源。

### 【5 边界与隐含要求】
- 断连起点的记录位置：写在 workload 状态（AC message 或时间字段）、MultiKueueCluster 的 Active 条件时间，还是 remoteClient 内存？重启 controller 后还要成立。
- 断连的 worker 可能是 workload 实际所在集群 (`status.clusterName`)，也可能是其他 worker；后者不应影响 workload。
- 所有 worker 都断连时不应因 `ErrNoActiveClusters` 而跳过超时处理（疑点 B）。
- 断连期间要反复 requeue，保证超时到点时有 reconcile 触发。
- 重连在超时内发生：workload 保持 Ready，重新找到 reserving remote，计时作废；同步远端 job 状态。
- 重连在超时后发生：既有测试“worker reconnects after the local workload is requeued, remote objects are deleted”（`workload_test.go:848`）要求清理远端对象，需保持。
- 其他仍连接的 worker 的 workload 不受影响。
- `stopAndRemoveCluster`（配置加载失败）会删除 client，使其表现为“集群不存在”，与临时断连不同。
- 弹性 workload、TAS、多 owner 的路径要不被影响。

### 【6 改动规模】
预计主要改 `workload.go` 一个文件的 2–3 处：`reconcileGroup` 第 6 步分支、`readGroup`/`remoteClientsForAC` 对全断连的处理，可能加上 `syncReservingRemoteState` 的时间记录。可能还有 1–2 处测试数据调整。多数情况下是局部修补，不新增 API；如果要把断连时间落到状态里，会稍微贯穿一层（cluster → workload）。

### 【7 难点一句话】
难点是看出“过早”源自计时起点用了 AC 变 Ready 的时间而非断连时间，并为“断连起点”选一个重启后仍成立、且不破坏现有测试语义的来源，同时处理全 worker 断连时 `ErrNoActiveClusters` 绕过超时逻辑的问题。