# 档案：MDC 上下文在 task/flow 日志中不一致（kestra-16067）

我读了 `Logs.java`、`LogsTest.java`、`RunContextLogger.java`、`LogEntry.java`、`StackdriverJsonLayout.java`，并 grep 了 MDC 的用法和 `Logs.*` 的调用点。没有跑测试，也没有查 git 历史（快照不是 git 仓库）。

## 【1 题面要点】
- **期望行为**：服务端的执行、任务、触发器日志也应该带 MDC 上下文，例如 tenantId、namespace、flowId、executionId、taskId、taskRunId。issue 说 0.19.5 有这个行为，1.0.3 里只有用户任务自己的日志（logger 名 `flow.xxx.hello`）带上下文。
- **复现**：只给了 logback 配置（`base.xml` + `gcp.xml` + `CONSOLE_JSON_OUT`）和一份 Hello World 的 JSON 输出。
  - 只有 `flow.gnu_170208.hello` 那行有 `taskRunId`、`tenantId` 等字段。
  - `execution.…`、`task.…` 这些服务端日志（"Flow started"、"Type Log started"、"completed in"）没有这些字段。
- **修法建议**：issue 里的原话是，本地调试时在 `LogService.java#L45` 的 `logExecution` 里加 `MDC.setContextMap(Map.of("tenantId", …, "namespace", …, "flowId", …, "executionId", …))`。
- **题面没写的**：没有预期输出，没有要求清理 MDC，也没有说明 task 和 trigger 要怎么处理。
- **类名对不上**：issue 里的 `LogService` 在本快照里不存在，对应的是 `core/.../utils/Logs.java`。

## 【2 相关代码】
- `core/src/main/java/io/kestra/core/utils/Logs.java`，这是服务端日志的统一入口，目前没有任何 MDC 调用：
  - `:26 logExecution(FlowId, Logger, …)`：只把 tenant、namespace、flow 拼进消息前缀。
  - `:36` / `:41 logExecution(Execution, …)`：前缀包含 execution。
  - `:50` / `:55 logTrigger(TriggerId, …)`：前缀包含 trigger。
  - `:64 logTaskRun(TaskRun, …)`：前缀包含 task、execution、taskrun，还有可选的 value。
  - `:76`、`:82`、`:88`：三个私有 `logger(...)` 方法，logger 名分别是 `worker.*`、`scheduler.*`、`executor.*`。
- `core/.../runners/RunContextLogger.java:194-202`：用户任务日志的参考做法。
  - 它给一个独立的 `LoggerContext` 配了自己的 `LogbackMDCAdapter`。
  - 用 `logEntry.toMap()` 设置上下文。
  - `resetMDC()` 在 `:239`，由 `DefaultRunContext.java:529` 调用。
- `core/.../models/executions/LogEntry.java:134 toMap()`：键是 tenantId、namespace、flowId、taskId、executionId、taskRunId、triggerId、executionKind，值为 null 的会被过滤掉。
- `cli/.../logger/StackdriverJsonLayout.java:37-38`：当 `includeMDC` 为 true 时，把 `event.getMDCPropertyMap()` 写进 JSON。读取端不需要改。

## 【3 并列与牵连】
- **四组并列方法需要同样处理**：flow 版 logExecution、execution 版、trigger 版、taskrun 版。只改 issue 里提到的 execution 版会漏掉另外三个。
- **调用点很多，但都经过 `Logs`**：
  - executor：`ExecutorService` 约 8 处，`DefaultExecutor:794`。
  - worker：`WorkerTaskProcessor:213` 和 `:352`，`WorkerTriggerProcessor` 多处，`ExecutionKilledManager`。
  - scheduler：`TriggerScheduler`、`TriggerEventHandler`、`SchedulableEvaluator` 等。
  - 其他：`PluginDefaultService:251`、`:308`，`ExecutionController:711`。
  - 如果在 `Logs` 内部改，调用点不用动。
- **线程污染风险**：
  - MDC 是线程局部的。executor 和 worker 线程会复用，MDC 设置后如果不清理，会漏到后面不相关的日志里。
  - `WorkerTaskProcessor` 里的任务日志用的是 `RunContextLogger` 自己的 `LoggerContext` 和 MDC 适配器，与全局 MDC 互不干扰。
  - 不过 `ForwardAppender` 把 flow 日志转发到服务端 logger 时，MDC 来自哪里需要确认。

## 【4 现有测试与约定】
- `LogsTest.java` 只断言数量和 logger 名：
  - `:53 assertThat(logs).hasSize(3)`
  - `:65 getLoggerName()).isEqualTo("executor.tenant.namespace.flow")`
  - `:77 …("scheduler.tenant.namespace.flow.trigger")`
  - `:91 …("worker.tenant.namespace.flow.task")`
- 测试用 `InMemoryAppender` 收集 `ILoggingEvent`，所以隐藏测试很可能加 `event.getMDCPropertyMap()` 断言：键名用 `tenantId`、`namespace`、`flowId`、`executionId`、`taskId`、`taskRunId`、`triggerId`，和 `LogEntry.toMap()` 一致。
- 与题面不冲突，现有测试没有 MDC 相关断言。
- **注意**：`:79` 那个 taskrun 用例没设 tenantId（null），隐藏测试可能会覆盖 null 值。`MDC.put` 对 null 值的处理取决于具体实现，要过滤掉。
- 仓库里没发现专门约定 MDC 的文档。

## 【5 边界与隐含要求】
- **清理 MDC**：日志输出后要恢复或清除，不能残留到线程里的下一条日志。try/finally，或者用 `MDC.putCloseable`。
- **恢复而不是清空**：issue 里的写法用的是 `MDC.setContextMap`，会覆盖调用者已有的上下文。更稳妥的做法是 put 单个键，之后只移除自己加的键。
- **null 值**：`MDC.put` 的 value 为 null 时，不同 MDC 适配器的行为不一致，要过滤。例如 `taskRun.getValue()`、tenantId 为 null，flow 版没有 executionId。
- **taskrun 版和 trigger 版**：要补上 taskId、taskRunId，以及 triggerId。
- **MDC 里是否放 value**：不确定。`LogEntry.toMap()` 里没有 value 这个键。
- **flow 版**：`FlowId` 没有 executionId，只能设 tenant、namespace、flowId。
- **executionKind**：`LogEntry.toMap()` 里有，但 `Execution` 版是否也要带上，题面没提。

## 【6 改动规模】
- 主改动：1 个文件，`Logs.java`，约 4 个方法，局部修补，不用新增结构。可以加一个私有辅助方法，比如 "put MDC → log → remove"。
- 测试：`LogsTest.java` 加 MDC 断言。
- 不需要改调用点、`StackdriverJsonLayout` 或 `RunContextLogger`。

## 【7 难点一句话】
改动本身很小。难点是上下文污染：线程会复用，所以 MDC 要在每次日志后正确清理，并且不能覆盖调用者已有的 MDC，同时 null 值要过滤，四个并列方法的键名要和 `LogEntry.toMap()` 一致，隐藏测试才能通过。