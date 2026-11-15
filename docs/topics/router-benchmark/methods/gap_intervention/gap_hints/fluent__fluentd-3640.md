## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 可能要一并处理的位置
1. `lib/fluent/plugin_helper/retry_state.rb` 里 `ExponentialBackOffRetry#calc_max_retry_timeout` 以 `i` 从 0 开始调用 `calc_interval(i)`，`calc_interval` 内部又对 `num` 减 1。这两处的下标约定要对齐，题面说的 -1 次幂就出在这里。
2. 同一个类里的 `naive_next_time(@steps)` 和 `calc_next_time` 的 secondary 分支 `naive_next_time(@steps - @secondary_transition_steps + 1)`，也都经过 `calc_interval`。初始 `@next_time = @start + @constant_factor` 是第一次重试，第一次 `step` 后 `@steps=1`，`calc_interval(1)` 对应 c*b^0，所以第一次和第二次重试间隔可能都是 c。先弄清哪一处才是真正偏移的，再改，只改 `calc_max_retry_timeout` 可能会和实际重试节奏不一致。
3. `calc_interval` 里的 inf 回退循环（`num -= 1; raw_interval(num-1)`）和 `max_interval` 封顶逻辑，改下标后也要保持一致。
4. `PeriodicRetry#calc_max_retry_timeout`（`wait*max_steps`）是并列实现，指数版本在 `backoff_base=1` 时应与它一致，可作参照。
5. `lib/fluent/plugin/output.rb:96` 附近的 `retry_exponential_backoff_base` 配置注释里有总时间公式，题面也要求文档说明第一次重试是 c 还是 c+c*b。公式和说明应与最终行为一致，该公式本身也很可能写错。

B. 可能被检查的边界输入
1. `max_steps` 为 0、1、2 时的总超时。1 步应该就是 c 本身，不应该是 c*b^-1。
2. 设置 `secondary` 时，`@secondary_transition_at` 由 `calc_max_retry_timeout(max_steps)` 与 `timeout` 取较小者再乘阈值得到，总超时变了，转换时间点也会变。
3. `max_interval` 很小或很大、`backoff_base` 取 1 或非整数、`randomize` 关闭时的结果。

C. 仓库已有约定
1. `test/plugin_helper/test_retry_state.rb` 已有大量按固定间隔序列断言 `next_time` 的用例，包括 secondary、max_interval、inf 的用例（约 432 行附近有 1024 的 inf 用例）。改下标前先看哪些断言依赖现有节奏，并核对它们是否已假设了正确值。
2. 同一文件里已有针对 `calc_max_retry_timeout` 或 `max_steps` 的测试，要检查期望值是否需要同步。
3. `test/plugin/test_output.rb` 和 `test/plugin/test_buffer*.rb` 等可能间接依赖重试时间，改完要跑。

D. 提交前建议自测
1. 用 `randomize=false`、wait=1、base=2，手算 `max_steps=1,2,3,4` 的总时间（应为 1、3、7、15），并和实际 `step` 序列累计的间隔对比。
2. 打开 `secondary` 加 `max_steps`，核对转换时间点是否和修正后的总超时一致。
3. 跑完整的 `test_retry_state.rb`，再检查 `max_interval` 封顶和 inf 回退用例是否仍通过。
