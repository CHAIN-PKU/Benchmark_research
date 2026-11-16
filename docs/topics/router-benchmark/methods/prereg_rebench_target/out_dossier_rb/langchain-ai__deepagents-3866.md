**档案：GLOB_TIMEOUT 在同步 glob 工具中不限制墙钟时间**

**【1 题面要点】**
- 要求的行为：同步 `glob` 工具超时后应在约 `GLOB_TIMEOUT` 秒内返回 "timed out" 错误，而不是阻塞到后台 glob 跑完。
- 题面给了完整复现脚本：patch `GLOB_TIMEOUT=0.5`，让 backend.glob 睡 3 秒。
- 期望输出："Expected: returns after ~0.5s (the timeout)"。实际是 "returns after ~3.0s"。
- 根因题面已经点明：`with ThreadPoolExecutor(max_workers=1)` 块里 `return`，触发 `__exit__` → `shutdown(wait=True)`，会 join 还在跑的线程。
- 次要问题："constructing a fresh `ThreadPoolExecutor` ... per glob call adds ~5x dispatch overhead vs. reusing a shared executor"。
- 题面没有给出明确的修法，只暗示用共享 executor，并且不能在 `with` 里等待 shutdown。
- 题面说 "No new interfaces are introduced."
- 题面称异步版 `async_glob` 不受影响。

**【2 相关代码】**
- `libs/deepagents/deepagents/middleware/filesystem.py:1247-1297` 是 `sync_glob`。
  - `:1271` 用 `contextvars.copy_context()` 拷贝上下文。
  - `:1272` 在 `with ThreadPoolExecutor(max_workers=1)` 里 submit，并用 `ctx.run(resolved_backend.glob, ...)` 调用。
  - `:1275` 是 `future.result(timeout=GLOB_TIMEOUT)`。
  - `:1276-1282` 捕获 `concurrent.futures.TimeoutError`，返回 error 的 ToolMessage。
  - 这个 `with` 块就是 bug 所在。
- `:233` 定义 `GLOB_TIMEOUT = 20.0`，是模块级常量，测试通过 patch 它来改超时。
- `:5` 有 `import concurrent.futures`。
- `:1299-1346` 是 `async_glob`，用 `asyncio.wait_for(aglob, timeout=GLOB_TIMEOUT)`，不需要改。

**【3 并列与牵连】**
- 同文件里只有这一处使用 ThreadPoolExecutor（grep 全 `deepagents/` 包确认）。
- 没有并列的同步超时实现。grep 和 execute 没有类似的线程超时。
- `backends/protocol.py:482` 有一处 `asyncio.wait_for`，是异步路径，与本题无关。
- 各 backend 的 `glob` 实现是被包装的对象，不需要改：
  - state.py:303
  - sandbox.py:832
  - filesystem.py:807
  - store.py:706
  - composite.py:405
  - context_hub.py:267
- 牵连点：
  - 共享 executor 是模块级或实例级状态，涉及线程生命周期。
  - 超时后线程仍在后台运行并占着 worker。如果共享池 `max_workers=1`，一个失控 glob 会堵住后续所有 glob，后续调用会排队并全部超时。
  - 池要有足够的 worker，或者每次超时后替换执行线程。

**【4 现有测试与约定】**
- 同步测试 `libs/deepagents/tests/unit_tests/test_middleware.py:414-436` `test_glob_timeout_returns_error_message`：
  - patch `GLOB_TIMEOUT` 为 0.5，让 `backend_obj.glob` 睡 2 秒。
  - 断言 `result.content == "Error: glob timed out after 0.5s. Try a more specific pattern or a narrower path."`。
  - 没有断言耗时，所以现有测试在 bug 存在时也能通过。
- 异步测试 `test_middleware_async.py:295-317` 断言同样的消息。
- 隐藏测试很可能新增耗时断言（如 elapsed < 睡眠时长），并可能测试连续调用或线程复用。
- 约定上要保持错误消息字符串不变，现有测试依赖它。
- 测试通过 `patch.object(filesystem_middleware, "GLOB_TIMEOUT", ...)` 在运行时读取模块全局，所以实现里必须在调用时读取 `GLOB_TIMEOUT`，不能在 import 时固化。
- 测试通过 `patch.object(backend_obj, "glob", ...)` 替换方法，所以必须经由 `resolved_backend.glob` 属性调用。
- 与题面期望没有冲突。

**【5 边界与隐含要求】**
- 超时后不能在 `with` 或 shutdown 里 join 线程。要用 `shutdown(wait=False)`，或者使用不 join 的共享池。
- 保留 contextvars 传播（`ctx.run`），因为 backend 可能依赖 runtime 上下文（如 StateBackend 通过 langgraph config 取 state）。
- 失控线程会泄漏并继续占用 worker：
  - 共享池 worker 数是否足够。
  - 多个并发 glob（并行 tool call）是否会互相排队。排队时间会被算进 `future.result(timeout)`，造成误超时。
- backend 抛异常时，`future.result` 会重新抛出，行为要与原来一致。
- 超时时可以考虑 `future.cancel()`，它只对未开始的任务有效。
- 线程池的创建要线程安全（惰性创建时加锁）。
- 进程退出时守护线程不应阻塞解释器。`ThreadPoolExecutor` 的线程在退出时会被 join，失控 glob 仍可能拖慢退出。如果要避免，可能要用 daemon 线程。
- 超时后的 `status="error"` 要保留。

**【6 改动规模】**
- 核心只改 `filesystem.py` 一个文件的约 10-20 行：新增共享 executor（模块级或惰性单例），并改写 `sync_glob` 中的 `with` 块。
- 测试文件可能新增 1-2 个用例，用来断言耗时。
- 属于局部修补，不需要贯穿多层。

**【7 难点一句话】**
修复本身很小，难点在于设计共享 executor 时要同时避免：返回时 join 线程、失控线程占满池导致后续 glob 排队误超时、contextvars 丢失。隐藏测试大概率会断言耗时和连续调用行为。