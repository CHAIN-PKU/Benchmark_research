**Pulsar dedup 恢复竞态 — 仓库档案**

**【1 题面要点】**
- 要求：`MessageDeduplication.checkStatus()` 在启用路径上先把状态置为 `Recovering` 再开始 replay。replay 进行中，并发的 `checkStatus()` 不能再启动第二次 replay。
- 要求：启用失败（状态变为 `Failed`）后，只要 policy 仍要求开启 dedup，后续 `checkStatus()` 要能重试启用。
- 题面没有给修法代码。关键句有三条：
  - "Deduplication should enter `Recovering` before starting recovery replay."
  - "Concurrent status checks should not start another recovery while replay is in progress."
  - "a later check should retry enabling when deduplication is still required by policy."
- 复现思路：让第一次 replay 延迟（延迟异步 openCursor 或 replay 完成），在完成前再调一次 `checkStatus()`，观察是否再次进入 enable 路径。
- 题面没有给期望输出。"No new interfaces"。

**【2 相关代码】**
- `pulsar-broker/.../service/persistent/MessageDeduplication.java`
  - `:67-86` `enum Status`：Initialized、Disabled、Recovering、Enabled、Removing、Failed。`Recovering` 已定义，但没有任何赋值处。
  - `:159-243` `checkStatus()`：整体在 `synchronized(this)` 内。
    - `:162` 遇到 Recovering 或 Removing 就在 1 分钟后重新调度 `checkStatus` 并返回已完成的 future。
    - `:227` 的 `(Disabled || Initialized) && shouldBeEnabled` 分支调用 `openCursor(...).thenCompose(this::replayCursor)`，**没有设置 status**。这是主要修改点。
    - `:231-236` 的 `exceptionally` 里设 `status = Failed`，并对已失败的 future 再调 `completeExceptionally`（冗余，且这个 future 是 thenCompose 的结果，没起作用）。
  - `:245-278` `replayCursor()`：先设置 `managedCursor`，再灌入 properties 快照，用 `replayTask.replay` 回放，最后在 `:274-276` `thenRun` 里设 `status = Enabled`。
  - `:280` `isEnabled()` 只认 Enabled。
  - `:167-188` Initialized 且不需要启用时的删除游标分支。它设 Removing，但**没有 return**，会继续往下走，且回调失败时不会把状态改回。这是相邻的既有瑕疵，题面没提。
- `PersistentTopic.java:2002` `checkDeduplicationStatus()` 直接委托给 `messageDeduplication.checkStatus()`。
- 调用点：
  - `PersistentTopic.java:3880`，`onUpdate` 里的 `applyPoliciesFutureList`。
  - `BrokerService.java:1967`，topic 加载链。

**【3 并列与牵连】**
- 并列实现：没有。Disable 分支（`:190`）已经用 `Removing` 做互斥，enable 分支是缺这一步。
- 两个调用点（`onUpdate` 与 `BrokerService`）都走同一个 `checkStatus()`，所以只改 `MessageDeduplication` 即可。
- 牵连：
  - 状态改成 Recovering 后，第二次调用会命中 `:162`，返回 `completedFuture` 并调度 1 分钟后重查。BrokerService 链会因此在 replay 未完成时就继续往下走，topic 在 dedup 未恢复时可能已对外服务。
  - 这时 `isEnabled()` 为 false，`isDuplicate` 会放行消息（`:292` 返回 NotDup）。恢复窗口内发布的消息不做 dedup，这个窗口原来就存在。
  - Failed 重试：`checkStatus` 里没有任何 Failed 的处理分支。`Failed → Removing`（disable 失败）这一路也会落入 Failed，因此重试条件要区分。需要决定 Failed 状态下 `shouldBeEnabled` 时是重新 enable，还是 `!shouldBeEnabled` 时尝试 disable。题面只要求前者。
  - 重试时 `managedCursor` 与 `highestSequenced*` 里可能留有半成品状态，replay 前最好清理，否则会残留脏数据。

**【4 现有测试与约定】**
- `pulsar-broker/src/test/.../BrokerMessageDeduplicationTest.java:114-132` `checkStatusFail`：mock 的 `asyncOpenCursor` 同步成功，`asyncReadEntries` 抛 `RuntimeException`。
  - 断言：`deduplication.checkStatus().get(3, SECONDS)` 抛 `ExecutionException`，`assertTrue(e.getCause() instanceof RuntimeException)`，`e.getMessage().contains("asyncReadEntries failed")`。
  - 这要求失败要把原异常通过返回的 future 传出，改动时不能破坏。
- 该测试类里没有对 Recovering 或 Failed 重试的断言。隐藏测试大概率是这个类里的新用例：延迟 openCursor，调两次 `checkStatus`，验证 `asyncOpenCursor` 只被调用一次、状态为 Recovering。再加一个让第一次失败、第二次成功的重试用例。
- `Status` 是包级私有的 enum（无 `public`），`getStatus()` 在 `:151`，测试可通过它读取状态。
- 与题面期望没有冲突。已有的 `Recovering` 注释 "Initializing deduplication state" 正是预期用法。
- 另外 `TopicTransactionBufferTest.java:171` 和 `TransactionPersistentTopicTest.java:141` 只是 mock/覆盖 `checkDeduplicationStatus`，与本题无关。

**【5 边界与隐含要求】**
- 同步异常：`openCursor` 或 `replayCursor` 若同步抛异常，状态必须转为 Failed，不能卡在 Recovering，否则会永久被 `:162` 的重调度占住。`checkStatusFail` 里 `asyncReadEntries` 同步抛异常就是这种情形。
- 失败要把状态置为 Failed，并让返回给调用者的 future 异常完成，保持异常类型和消息。
- Failed → 重试时，状态应先回到 Recovering，再走同一个启用流程。
- 重试前清理 `managedCursor` 与 `highestSequencedPushed/Persisted`，避免遗留。
- 失败后若 `!shouldBeEnabled`，不应误重试。
- 并发调用时，第二次返回的 future 应该是已完成状态（现有 Recovering 分支如此），而不是等待第一次完成。是否改成共享同一个 recovery future，题面未说。
- 状态写入在 `synchronized` 内，而回调里（`:232`、`:275`）的写入不在锁内，靠 volatile 可见性。
- 并发 checkStatus 在 `:164` 会为 Recovering 重复调度 1 分钟后的任务，可能累积调度，影响不大。

**【6 改动规模】**
- 主要改 1 个文件 `MessageDeduplication.java`，集中在 `checkStatus` 的 enable 分支（约 10–20 行）。
- 在该分支加 `status = Recovering`，并把 Failed 加入启用条件。
- 视情况加一个 try/catch 处理同步异常，并修正 `exceptionally` 的写法。
- 局部修补，不需要新增结构，也不需要贯穿多层。另需新增测试。

**【7 难点一句话】**
改动本身很小（置 Recovering 并让 Failed 参与重试），难点在于：必须保证所有失败路径（含同步异常和回调失败）都能退出 Recovering，否则状态会永久卡死；同时要保住 `checkStatusFail` 的异常传播语义，并处理好 Failed 重试时的残留状态。