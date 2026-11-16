**档案：`retry_max_times 0` 时仍重试一次（fluentd，retry_state / output.rb）**

**【1 题面要点】**
- 要求的行为：配置 `retry_max_times 0` 后，首次 flush 失败不应再重试，应直接丢弃队列。
- 复现：只有一段 buffer 配置（`retry_max_times 0`、`retry_wait 3s`、`retry_timeout 100s`、`retry_max_interval 30s`、`retry_forever false`）和日志，没有最小复现脚本。
- 日志现象：第一次失败打印 `failed to flush the buffer. retry_time=0 next_retry_seconds=…+3s`，3 秒后同一 chunk 再失败，才打印 `hit limit for retries ... retry_times=0`。作者的结论是 `retry_max_times` 没生效，而 `retry_wait` 生效了。
- 期望输出和修法建议：题面没有给出。issue 文本在日志中途被截断。

**【2 相关代码】**
- `lib/fluent/plugin_helper/retry_state.rb:134-140` `limit?`：`@next_time >= @timeout_at || !!(@max_steps && @steps >= @max_steps)`。`max_steps` 为 0 时 `steps(0) >= 0` 本来为真。
- `lib/fluent/plugin/output.rb:1271-1318` `update_retry_state`：这是真正的触发点。
  - 第一次失败时 `@retry` 为 nil，走 1276-1283 分支，创建 retry 状态并打印 warn 后直接 `return`，没有检查 `limit?`。
  - 只有第二次失败（`@retry` 已存在）才在 1287 检查 `limit?`，命中后清队列（`clear_queue!`）并置 `@retry = nil`。
  - 所以 `max_steps=0` 时，首次失败总会多重试一次。
- `lib/fluent/plugin/output.rb:1320-1337` `retry_state`：把 `retry_max_times` 作为 `max_steps` 传入，有无 secondary 各一处。
- `retry_state.rb:20-33` `retry_state_create`、`:38-71` 构造函数、`:120-128` `step`：构造函数里 `if max_steps` 对 0 也为真（Ruby 中 0 是 truthy），且 `calc_max_retry_timeout(0)` 在 secondary 开启时返回 0。
- `retry_state.rb:151,196`：两个子类构造函数都把 `@next_time` 初始化成 `@start + wait`，也就是首次重试的时间。
- `output.rb:84` `retry_max_times` 默认 `nil`，没有 `0` 的特殊处理。

**【3 并列与牵连】**
- 并列实现：`ExponentialBackOffRetry`（143-188）和 `PeriodicRetry`（190-206）都继承 `RetryStateMachine`，`limit?` 在基类里，所以只改基类即可覆盖两种。
- `output.rb:1330` 与 `1322` 两处 `retry_state_create` 调用相同，但逻辑上是同一入口。
- `retry_state` 只在 `output.rb` 里被调用。
- 牵连点：
  - `output.rb:852`、`1133`、`1362`、`1481` 用 `@retry` 是否存在、`@retry.next_time` 决定 flush 时机。
  - `1067-1073` 成功后把 `@retry` 置 nil。
  - `1093/1109/1124` 的 `primary.update_retry_state` 在 secondary 路径里也会调用，行为需保持一致。
  - 兼容参数 `retry_limit` 映射到 `retry_max_times`（`compat_parameters.rb:36`）。

**【4 现有测试与约定】**
- `test/plugin_helper/test_retry_state.rb:81-105`（periodic，max_steps 5）：循环 step 到 `steps=5` 后断言 `assert s.limit?`，之前每步 `assert !s.limit?`。`:281-329` 对 exponential 有同样的断言。这些测试都只覆盖 `max_steps >= 1`，没有 0 的用例。
- `test/plugin/test_output_as_buffered_retries.rb:621-703`（`retry_max_times 10`）：断言日志含 `hit limit for retries` 且 `retry_times=10`。这说明现有语义是"先失败一次，再重试 10 次，共 11 次尝试"。因此 `retry_times=N` 表示 N 次重试，0 就应该是"不重试"。同文件 338、425 行也是类似用例。
- 现有测试没有 `retry_max_times 0` 的用例；隐藏测试大概率会在 `test_output_as_buffered_retries.rb` 里新增，或者在 `test_retry_state.rb` 里新增 `max_steps: 0` 的用例。
- 文档约定：`output.rb:84` 的描述是 "maximum number of times to retry"，所以 0 应当是不重试，与题面期望一致，没有冲突。

**【5 边界与隐含要求】**
- 首次失败路径（1276-1283）需要检查 `limit?`。命中时要像 1287-1296 那样丢弃队列，并且日志要打印 error 级别的 "hit limit"，而不是 warn。
- `@retry` 创建后如果立刻命中限制，是否保留还是置 nil，要避免 `@retry` 残留导致 `1133`、`1362` 的 flush 调度出错。
- `max_steps` 为 nil 与 0 必须区分。构造函数和 `limit?` 里不能用真值判断来区分，否则 0 会被当成无限制。
- `retry_forever true` 时仍应忽略 `retry_max_times`（测试 723、794 行）。
- 有 secondary 时，`max_steps=0` 的转换阈值怎么算：`calc_max_retry_timeout(0)=0` 会让 `secondary_transition_at == @start`，要确认首次失败是否应直接转入 secondary。
- 还要确认 `limit?` 里 `@next_time` 在首次时是否已经 `>= timeout_at`（`retry_timeout` 很小的情形）。
- 并发：多个 flush 线程会同时进入 `update_retry_state`，都受 `@retry_mutex` 保护，需保持。
- 隐含需求：如果只改 `update_retry_state` 首次分支，要检查日志格式 `retry_times=0` 与现有测试断言一致。

**【6 改动规模】**
- 核心改动集中在 `output.rb` 的 `update_retry_state`，大概 1 个文件 1-2 处，需要新增一次 `limit?` 检查（或抽成共用逻辑）。
- `retry_state.rb` 可能顺带需要调整，但只是局部修补。
- 不涉及新结构，也不贯穿多层。再加测试文件 1-2 个。
- 总体是局部修补。

**【7 难点一句话】**
根因不在 `limit?` 本身，而在 `output.rb:1276-1283` 的"首次失败只建状态、不判限制"分支，所以难点是找对位置，并让"首次失败即命中限制"时的丢弃队列、日志和 `@retry` 状态与已有分支保持一致，同时不破坏 secondary 和 `retry_forever` 路径。