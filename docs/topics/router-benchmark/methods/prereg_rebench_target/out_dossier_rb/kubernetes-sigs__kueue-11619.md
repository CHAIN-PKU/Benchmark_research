**档案：独立 RayCluster 自更新 `raycluster-generation` 注解**

重要提醒：当前快照里 `RayCluster` 类型没有实现 `GetCustomAnnotations`，也没有实现 `GetWorkloadNameExtraPart`。issue 说的"独立 RayCluster 调用 `GetWorkloadslicingRayClusterCustomAnnotations(ctx, c, j.Object(), podSets, j.Name)`"在本快照里找不到。我在 `pkg` 下全量搜了 `GetCustomAnnotations` 和 `GetWorkloadNameExtraPart`，只有 RayJob 和 RayService 两处实现，`raycluster_controller.go` 里一处都没有。这和题面前提有出入，agent 要先确认这一点。

**【1 题面要点】**
- 要求的行为：独立的、开启 elastic 的 RayCluster，在副本数没变时不应被 Kueue 持续 patch。独立 RayCluster 不应把自己的 generation 写回自己。
- 现象：`metadata.generation: 273390`，注解值 `"273389"`，始终落后一位。
- 复现步骤：给出了（ElasticJobsViaWorkloadSlices=true，RayCluster 带 `elastic-job` 注解和 queue-name 标签）。
- 修法建议原句："A fix is to omit `kueue.x-k8s.io/raycluster-generation` when the `jobObject` is the same standalone RayCluster as `rayClusterName`."
- 题面没给期望输出的具体断言，也没说接口变化（"No new interfaces"）。

**【2 相关代码】**
- `pkg/controller/jobs/raycluster/common.go:335` `GetWorkloadslicingRayClusterCustomAnnotations`：
  - 开启 workload slicing 时，先 `c.Get` 取 `rayClusterName` 对应的 RayCluster。
  - 把其 generation 作为 `RayClusterGenerationAnnotation`（第 362 行）返回，同时返回 `RayClusterPodsetReplicaSizesAnnotation`。
  - NotFound 时 generation 为 `""`，但键仍然存在。
- `common.go:287` `GetWorkloadNameExtraPart`：用对象自身的 generation，再拼上 `"_" + 注解值`（注解非空时）。
- `pkg/controller/jobframework/reconciler.go:961-974`：
  - 调用 `GetCustomAnnotations`，再用 `mergeAnnotations`（第 1828 行）比较。
  - 只要有差异就 `clientutil.Patch`。
  - 这是自触发循环的机制：写注解 → generation 增加 → 注解过期 → 再写。
- `reconciler.go:1437`：用 `GetWorkloadNameExtraPart` 生成 elastic workload 名。

**【3 并列与牵连】**
- 并列调用点：
  - `rayjob_controller.go:215-216`，传 `j.Status.RayClusterName`。
  - `rayservice_controller.go:226-227`，传 `j.Status.ActiveServiceStatus.RayClusterName`。
  - 这两处的 jobObject 是 RayJob/RayService，不是 RayCluster，必须保留生成注解。
- 独立 RayCluster 的入口在快照里缺失（见上文提醒）。需要查它是通过别的路径调用，还是 agent 得新增 `RayCluster.GetCustomAnnotations`。
- 如果加了判断，`GetWorkloadNameExtraPart` 对独立 RayCluster 就不再带 `_gen` 后缀。这会影响 workload 名，也和 #10160 的"按 generation 命名"有关。
- 接口 mock 在 `internal/mocks/controller/jobframework/interface.go`，只有改接口签名时才需要动。

**【4 现有测试与约定】**
- `common_test.go:1085` `TestGetWorkloadslicingCustomAnnotations`，对象是 ConfigMap 包装，`rayClusterName` 为 "test-raycluster"：
  - 第 1116-1119 行断言 `RayClusterGenerationAnnotation: "0"` 和副本数 JSON。
  - 第 1165-1167 行：NotFound 时断言 `RayClusterGenerationAnnotation: ""`。
- `rayjob_controller_test.go:796-847` 有四处断言生成注解为 `"0"`。
- 隐藏测试很可能新增一个用例：jobObject 本身就是同名 RayCluster 时，返回的 map 只含副本数注解，没有 generation 键。
- 现有 ConfigMap 用例的 jobObject 与 rayClusterName 不同，应保持不变。
- 与题面期望没有冲突。

**【5 边界与隐含要求】**
- "同一对象"的判断：要比较 namespace、name，最好还要比较类型，避免 RayJob 恰好与其 RayCluster 同名时误判。
- 如果省略键，`mergeAnnotations` 只会新增或修改，不会删除。已被写入的旧注解会留在对象上，`GetWorkloadNameExtraPart` 仍会读到它。是否要清理、命名是否会变，需要考虑。
- 省略后可以跳过 `c.Get`，既省一次读取，也避免 NotFound 分支。
- 副本数注解本身没变时不应触发 patch（`mergeAnnotations` 已处理）。
- 要保证 RayJob 和 RayService 的行为不回归。

**【6 改动规模】**
- 小：1 个源文件（`common.go`）、1 个函数里加一个判断，另外在 `common_test.go` 加 1 到 2 个用例。
- 如果还要给 RayCluster 补 `GetCustomAnnotations` 之类的方法，则多改 `raycluster_controller.go`。

**【7 难点一句话】**
修法本身很简单，难点是快照里独立 RayCluster 的调用路径对不上题面，要先弄清是哪个入口触发了循环，再决定"同一对象"怎么判断，才能不影响 RayJob 和 RayService。