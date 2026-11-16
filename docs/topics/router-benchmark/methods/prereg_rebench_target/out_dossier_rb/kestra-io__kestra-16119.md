**档案：TriggerSchedulerMonitor 把实时触发器报告为锁定**

**【1 题面要点】**
- 期望行为：监控器不应再把 realtime 触发器当作"被锁定、没有 execution"的 trigger 反复告警。
- 现象（原文）："No execution found, schedule is blocked since '2026-04-27T13:38:23.415498Z'"。
- 原因（原文）："those trigger will always be blocked without any executionID they will be reported indefinitly."
- 没有复现步骤，也没有修法建议。"No new interfaces are introduced."，所以不新增接口，是行为修正。
- 隐藏测试大概率针对 `TriggerSchedulerMonitor`。目前没有该类的测试，可能是新增的。

**【2 相关代码】**
- `scheduler/src/main/java/io/kestra/scheduler/TriggerSchedulerMonitor.java:50-101`：`run()` 每 10 秒执行一次。
  - :56 调 `triggerStateStore.findTriggersEligibleForScheduling(now, vnodes, true)` 取所有 locked 的 trigger。
  - :63 用 `executionRepository.findAllByTrigger(state)` 查 execution。
  - :64-81 没有 execution 时记录 missing-duration 指标，updatedAt 超过 60 秒则 WARN。这就是题面的那条日志。
  - :82-96 有 execution 时记录 lock-duration 指标和 debug 日志。
- 最直接的修法是在遍历处（:61 之后）跳过 `state.getType() == TriggerType.REALTIME` 的 trigger。
  - 备选：在查询里排除 realtime（`AbstractJdbcTriggerRepository.java:315-330`）。这会同时影响 `DefaultSchedulableTriggerFetcher:66`，风险更大，不推荐。
- `core/.../scheduler/model/TriggerType.java:11-25`：枚举含 `REALTIME`，由 `TriggerType.from(trigger)` 按 `RealtimeTriggerInterface` 判定。
- `TriggerState.java:46` 有 `type` 字段，状态里已经带类型，不需要新结构。
- `TriggerScheduler.java:373-381`：`processWorkerTrigger` 里 `mustBeLocked = trigger instanceof RealtimeTriggerInterface || !isAllowConcurrent()`。realtime 一律 locked=true，也就是 bug 的来源。

**【3 并列与牵连】**
- `TriggerState.type` 同时可能是 SCHEDULE、POLLING、REALTIME 三类。
  - Polling 触发器在 `!allowConcurrent` 时也会被锁，这类仍有 execution，应继续监控。
  - Schedulable 同理（`TriggerScheduler.java:344`）。
- 仓库里只有 `TriggerSchedulerMonitor` 一处调用 `findAllByTrigger`（`:63`），没有成对的监控实现。
- 指标 `METRIC_SCHEDULER_EXECUTION_MISSING_DURATION` 和 `METRIC_SCHEDULER_EXECUTION_LOCK_DURATION` 也都在这里发出。跳过 realtime 后，这两个指标对 realtime 也不再产生。
- `TriggerEventHandler.java:368` 是 `TriggerType.REALTIME` 的另一处使用，是 `onTriggerDeleted` 里发 kill 事件，与本题无关，仅作参考。

**【4 现有测试与约定】**
- 没找到 `TriggerSchedulerMonitor` 的现有测试（Glob 无匹配）。
- 相关测试：
  - `scheduler/src/test/.../TriggerEventHandlerTest.java:154`：`TriggerState.of(triggerId, TriggerType.REALTIME, null, false, 0)`。
  - `TriggerSchedulerTest.java:734`：`TestRealTimeTrigger` 可复用来造 realtime 状态。
  - `AbstractTriggerRepositoryTest.java:447` 测 locked=true 的查询。
- `InMemoryTriggerStateStore.java:23-33` 可供测试使用。它按 `ts.isLocked() == locked` 过滤，与 JDBC 实现略有差异：JDBC 允许 `LOCKED_FIELD` 为 null，in-memory 不允许。
- 没发现与题面冲突的约定。

**【5 边界与隐含要求】**
- `state.getType()` 可能为 null（旧数据或手工构造的状态）。要用 `TriggerType.REALTIME.equals(state.getType())`，不能写 `.getType().equals`。
- 是完全跳过，还是只跳过告警，题面没说。
  - 若 realtime 也没有 execution，指标会误报，所以推荐整体跳过。
  - 测试可能断言 `executionRepository` 不被调用，或指标不被记录，或日志不被输出。
- 非 realtime 的 locked trigger 的原有行为必须保持不变：无 execution 且超过 60 秒时仍要 WARN。
- realtime 触发器是否可能产生 execution，题面没说。如果有，可能只想屏蔽"无 execution"的告警而保留其他监控。这是一个需要确认的歧义。

**【6 改动规模】**
- 1 个文件、约 3-5 行（加类型判断）。
- 测试大概率新增一个 `TriggerSchedulerMonitorTest`。
  - 构造函数需要 `MetricRegistry`、`ExecutionRepositoryInterface`、`TriggerStateStore`、`DefaultScheduler`，可 mock。
  - 或者给 monitor 加包可见的辅助方法，也是局部修补。
- 没有新结构，也不需要贯穿多层。

**【7 难点一句话】**
修法本身几乎是一行判断，难点只在于确认"跳过"的范围：只跳过 realtime、保持其他类型原行为，并让隐藏测试对日志、指标和仓库调用的断言都满足。