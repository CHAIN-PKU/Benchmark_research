# 仓库档案：woodpecker #6623（k8s 后端服务步骤一直显示 running）

注：我没有真实 k8s 环境。下面"为什么卡住"是读代码推断出的最可能原因，没有运行验证。

## 【1 题面要点】
- 期望行为：流水线的普通步骤跑完后，服务（service）步骤应被收尾，API 和 UI 不再显示 `running`。原文是 "Pipeline services are stopped once the pipeline steps complete, the pipeline completes."
- 现象：k8s 的 Pod 已被销毁，但服务步骤仍是 `state=running`、`Stopped: 0`。整个流水线要等超时才结束，forge 状态也不变绿。
- 题面给了：k8s 后端的 YAML 复现（postgres 服务加一个等待步骤），以及 API 输出。
- 题面没有给：修法建议、期望的具体状态值、日志。
- Interface 一节写 "No new interfaces are introduced."，所以是行为修复，不加新 API。
- 版本说明：3.14.x 出现的回归，next-d05c597374 上可复现。

## 【2 相关代码】
最可能的根因链（推断）：
- `pipeline/runtime/workflow.go:35-86` `Runtime.Run`：所有 stage 跑完后先调 `destroyWorkflowFunc()`（78 行），再 `r.uploadWait.Wait()`（82 行），最后才返回。返回之后 agent 才会报 `Done`（`agent/runner.go:210`）。
- `pipeline/runtime/step.go:227-258` `runDetachedStep`：每个服务步骤在后台 goroutine 里跑 `completeStep`，里面调 `engine.WaitStep`，并持有 `uploadWait`（236-238 行）。服务的 `WaitStep` 不返回，`Run` 就一直卡在 `uploadWait.Wait()`，`Done` 永远发不出去。
- `pipeline/backend/kubernetes/kubernetes.go:282-359` `kube.WaitStep`：
  - 只注册了 informer 的 `UpdateFunc`（313-317 行），只在 Pod phase 为 Succeeded/Failed/Unknown，或镜像拉取失败时才 `close(finished)`（305-309 行）。
  - 没有 `DeleteFunc`。`DestroyWorkflow` 把 Pod 删掉后不会再有 Update 事件，`WaitStep` 一直阻塞。它的退出路径只有 `ctx.Done()`（325-329 行），而传入的 `r.ctx` 此时并未取消。
  - 这也解释了为什么只有超时后才被清理。
  - 就算被唤醒，后面还有两步：Pod 已 Get 不到会返回 err；`cs.State.Terminated == nil` 也返回 err（346-350 行）。
- `pipeline/backend/kubernetes/kubernetes.go:474-501` `DestroyWorkflow`，以及 `pod.go:736-750` `stopPod`：删除 Pod，遇到 404 直接当成功。
- `pipeline/backend/docker/docker.go:278-314` `docker.WaitStep`：用 `ContainerWait`，容器被删或停都会返回。这是 k8s 缺少的行为，可作对照。

服务端（已有兜底，大概率不是主因）：
- `server/rpc/rpc.go:296-411` `Done`，其中 350 行调 `completeChildrenIfParentCompleted`（536-548 行）。它把仍在 Running 的子步骤用 `UpdateStepToStatusSkipped(..., StatusKilled)` 更新，已开始的会变成 `success` 并写入 `Finished`。
- `server/pipeline/step_status.go:154-161` `UpdateStepToStatusSkipped`。
- 所以只要 `Done` 到达服务端，服务步骤就不会再是 running。问题在于 `Done` 到不了。

## 【3 并列与牵连】
- 同样的 `WaitStep` 阻塞可能影响所有 `Detached` 步骤，不只是 `StepTypeService`（`runDetachedStep` 通用）。
- k8s 里 `WaitStep` 和 `TailStep`（`kubernetes.go:362-447`）是成对的 informer 写法，`TailStep` 也只有 `UpdateFunc`。不过日志流在 Pod 删除后会自然 EOF，大概率没问题。
- `DestroyStep`（449-471 行）在 `completeStep` 里 `WaitStep` 之后才被调用，所以 `WaitStep` 必须先返回。
- 后端接口契约在 `pipeline/backend/types/backend.go:112-138`，写明 `WaitStep` "blocks until completion"，`DestroyStep` 在 WaitStep 之后或取消时调用。
- 改 `WaitStep` 会牵涉：
  - k8s 里普通（非 detached）步骤的正常路径和取消路径。
  - `kubernetes_test.go` 里的 `TestWaitStepReturnsOnContextCancel`、`TestWaitStepNoGoroutineLeak`（informer goroutine 泄漏检查）。
- 备选修法（在 runtime 层）：`Run` 在 destroy 之后取消一个 detached 专用 ctx，让所有后端的 `WaitStep` 都返回。这会改动 `Runtime` 的 ctx 结构，并影响所有后端和 `runtime_test.go`。

## 【4 现有测试与约定】
- `pipeline/runtime/runtime_test.go:1408-1437` `TestWorkflowUnboundedServiceDoesNotHang`：注释写明 "a long-running service does NOT keep the workflow blocked forever. The runtime must tear the service down on its own"，并且是对 commit 4dd3be7f96 的回归测试。断言是 500ms 内 `Run` 返回 `NoError`。它用 dummy 后端，dummy 的 `DestroyWorkflow` 大概率会让 `WaitStep` 返回，所以抓不到 k8s 的问题。
- `runtime_test.go:1307-1354`：服务失败不影响工作流，并断言 "detached step exit trace must be emitted before Run() returns (uploadWait contract)"。因此 `uploadWait` 的约定要保留，修复不能简单地删掉它。
- `server/rpc/rpc_test.go:116-150` `TestCompleteChildrenIfParentCompleted`：断言运行中的服务被置为 `StatusSuccess`、`Finished == 1234567900`，工作流最终是 success。
- `server/pipeline/step_status_test.go:300-308`：`AlreadyStarted` 期望 `StatusSuccess`、`Finished == 100`。
- `pipeline/backend/kubernetes/kubernetes_test.go:227-258`：用 fake client 测 `WaitStep` 的 ctx 取消。隐藏测试很可能加在这里，例如：删除 Pod 后 `WaitStep` 应当返回，或返回 `Exited` 状态。
- 与题面不冲突。题面想要的"服务不再 running"和现有契约一致。
- 外部规范：k8s 的 watch 语义是删除事件走 `DeleteFunc`，Update 不会触发。

## 【5 边界与隐含要求】
- Pod 在 `WaitStep` 开始前就已被删或不存在：`Get` 会 NotFound，要决定返回错误还是返回"已退出"状态。
- Pod 被删时 `ContainerStatuses` 为空，或 `Terminated == nil`（350 行附近），不能让它变成错误。
- 服务被我们主动杀掉，退出码可能是 137 或 143，会被判成 `failure`。但根据 `step_status.go:85-88`，`Exited` 加非 0 退出码会变 `StatusFailure`，而 `runDetachedStep` 只记录日志，不影响工作流。需要确认最终显示的是 success 还是 failure，以及工作流状态是否仍为 success（`WorkflowStatus` 会按 `Failing()` 合并）。
- 服务端已兜底，但如果服务的 `Exited` trace 在 `Done` 之后才到达：`checkWorkflowAllowsStepUpdate`（`server/rpc/sanitize.go:103-119`）会放行，随后 `CalcStepStatus` 因步骤已是 success 而返回 "does not expect rpc state updates"，只是记录日志。
- 取消路径（`ctx.Done`）不能被改坏，informer goroutine 不能泄漏。
- 多服务、多 Pod 场景，以及 `Detached` 的非服务步骤。
- 多 Pod 共享的 informer：`WaitStep` 每次新建一个 SharedInformerFactory，要保证 `stop` 被关闭。

## 【6 改动规模】
- 最小修法：`kubernetes.go` 里 `WaitStep` 加 `DeleteFunc`，约 1 处、10~30 行。再加一个 `kubernetes_test.go` 测试。局部修补。
- 若走 runtime 层修法：`workflow.go`、`step.go` 约 2~3 处，要引入 detached 专用 ctx，牵连所有后端。
- 总计约 1~3 个文件，加测试。

## 【7 难点一句话】
难在定位：服务端已有清理逻辑、dummy 测试也能通过，真正的缺陷在 k8s `WaitStep` 对 Pod 删除没有反应，导致 `Run` 卡在 `uploadWait.Wait()`、`Done` 发不出去；定位后修法本身不大，但需要在不破坏取消路径和 goroutine 泄漏测试的前提下，决定 Pod 被删时该返回什么状态。