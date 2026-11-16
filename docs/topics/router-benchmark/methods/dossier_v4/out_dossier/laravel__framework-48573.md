**档案：ArrayStore 的 TTL 比指定值短（Laravel 10.25.0）**

注意：快照里的 `ArrayStore::get` 已经是 `>`（`ArrayStore.php:60`），所以 issue 里 diff 的那一半在此快照已经存在。问题没有消失，因为过期时间仍然截断为整数秒。

**【1 题面要点】**
- 期望行为：`put('hello', 1, 1)` 后立刻 `get('hello')` 必须稳定返回值。TTL 不能短于指定的秒数。
- 症状：`put` 和 `get` 之间只隔几微秒，只要跨过整秒边界，就会被判为过期。
- 复现脚本：`$cache->put('hello', 1, 1); echo $cache->get('hello');`，题面称"it all depends on the startup time (microseconds)"。
- 作者给的两个修法：
  - "currentTime must return microtime(true) and expiresAt should be in microseconds for array cache"
  - "rollback changes MR #48497"
- 作者本地改动是把 `>=` 改成 `>`：
  - 这一改动只是缓解。
  - 题面没有给出期望输出，也没有测试。

**【2 相关代码】**
- `src/Illuminate/Cache/ArrayStore.php:50-67`（`get`）：用 `$this->currentTime() > $expiresAt` 判断过期，两边都是整数秒。
- `ArrayStore.php:178-192`：
  - `calculateExpiration` 调 `toTimestamp`。
  - `toTimestamp` 对 `$seconds > 0` 返回 `$this->availableAt($seconds)`，否则返回 0（永不过期）。
- `src/Illuminate/Support/InteractsWithTime.php:31-38`：`availableAt` 返回 `Carbon::now()->addRealSeconds($delay)->getTimestamp()`，小数秒在这里被截断。
- `InteractsWithTime.php:60-63`：`currentTime()` 返回 `Carbon::now()->getTimestamp()`，也是整数。
- 截断的后果（`>` 不能根治）：
  - 在 t=100.9999 执行 `put(..., 1)`，`expiresAt` 为 101。
  - 在 t=101.0001 执行 `get`，`currentTime()` 为 101。
  - 此时 `101 > 101` 为假，仍有效，但实际只存活了约 0.0002 秒。
  - 在 t=102.0 时才过期，此时已存活约 1.0001 秒。
  - 所以 TTL 实际落在 [0,1) 到 [1,2) 之间，整体偏短。

**【3 并列与牵连】**
- `ArrayLock.php:39-47` 已经用 `Carbon::now()->addSeconds(...)` 和 `isFuture()`，保持完整精度。锁部分基本不需要改，但要和存储保持一致。
- `InteractsWithTime` 是共享 trait，下面这些类都在用，改它会波及这些类：
  - `FileStore.php:120,303,320,356`
  - `DatabaseStore.php:117,258`
  - `Lock.php:115,120`
  - `RateLimiter.php:119,212`
  - `MemcachedStore.php:246`
  - `DynamoDbStore.php:471`
  - 队列、Bus 等其他模块。
- 因此更安全的做法是只在 ArrayStore 内局部改，不动 trait。
- Memcached、Dynamo、File 和 Database 这些存储需要整数时间戳，所以 trait 不应改动。
- `ArrayStore` 的 `increment` 通过 `get` 判断过期，`many` 通过 `RetrievesMultipleKeys` 调用 `get`，两者随 `get` 一起受益。
- 其他 `ArrayStore` 子类或测试里如果 mock 了 `calculateExpiration`、`toTimestamp`，可能受影响，我没有逐个确认。

**【4 现有测试与约定】**
- `tests/Cache/CacheArrayStoreTest.php:51-55`：`put('foo','bar',10)`，把测试时间推到 `now()->addSeconds(10)->addSecond()`，断言 `get` 为 null。
- `CacheArrayStoreTest.php:122-126`：`put('foo',999,10)` 后推进 11 秒，`increment` 得到 1。
- `CacheArrayStoreTest.php:177-187`：锁获取 10 秒后，时间推到 `+10`，断言 `acquire()` 为 true。这说明锁在恰好 10 秒时视为过期。
- `CacheArrayStoreTest.php:189-199`（`testLockExpirationLowerBoundary`）：时间推到 `+10 秒 -1 微秒`，断言 `acquire()` 为 false。
- 以上测试都用 `Carbon::setTestNow` 冻结时间，所以隐藏测试很可能也这样写，比如在 `+TTL-1 微秒` 时断言值仍存在。
- 与 issue 的冲突：issue 作者的 `>` 补丁会让"恰好 TTL 秒时仍存在"，而锁的约定是"恰好 TTL 秒时已过期"。键值存储和锁的边界语义可能不一致。
- 没有外部规范，约定以其他存储为准。其他存储都是整数秒。

**【5 边界与隐含要求】**
- `$seconds` 可能是 `DateTimeInterface` 或 `DateInterval`，目前 `availableAt` 已通过 `parseDateInterval` 处理，改后要保留。
- 如果 `$seconds` 是小数（例如 0.5），也要工作。
- TTL 为 0 或负数的约定：
  - `toTimestamp` 对 `<=0` 返回 0（即"永不过期"）。
  - `get` 里 `$expiresAt !== 0`，如果过期值改成 float，要注意 `0.0 !== 0` 的严格比较。
- `Carbon::setTestNow` 必须仍然有效。如果改用 `microtime(true)`，现有冻结时间的测试会全部失效。必须通过 `Carbon::now()` 取微秒，例如 `Carbon::now()->getPreciseTimestamp(...)`，或用 `getTimestamp() + microsecond/1e6`。
- `forever` 和 `increment` 路径要保持"永不过期"，不能被新的时间表示破坏。
- 序列化存储（`serializesValues`）路径不受影响。
- 缓存的 `get`/`put` 对 `ArrayStore` 的 `expiresAt` 键是否被外部直接读取，需要确认。

**【6 改动规模】**
- 实际只需要改 `ArrayStore.php` 一个文件，约 2~3 处：`calculateExpiration`/`toTimestamp`（改为返回带小数秒的值）和 `get`（用相同精度的当前时间比较）。
- 局部修补，不需要新增结构。
- 不修改 `InteractsWithTime`，否则会贯穿多个存储。
- 另外还要加一个测试。

**【7 难点一句话】**
难点在于不改动共享的 `InteractsWithTime`，只在 `ArrayStore` 内同时做到微秒精度和 `Carbon::setTestNow` 兼容，同时保留 `0 = 永不过期` 的哨兵值，并保证现有边界测试（含锁的 `+10s`/`-1µs`）不被破坏。