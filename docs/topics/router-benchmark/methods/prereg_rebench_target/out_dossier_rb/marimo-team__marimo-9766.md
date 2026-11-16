我已经查完相关代码和测试，下面直接给出档案。

# 仓库档案

## 【1 题面要点】
- 要求的行为有两条：
  - 不使用 `mo.Thread` 的笔记本里，`print` 必须保持内建对象身份（`print is builtins.print`），这样 Numba 才能编译调用它的函数。
  - `mo.Thread` 仍须把输出路由到启动它的 cell，并行线程之间输出互相隔离。
- 题面没有复现脚本、期望输出或修法建议。
- 关键句：“In notebooks that do not use `mo.Thread`, `print` must retain builtin identity”；“`mo.Thread` must continue routing output to the spawning cell, with output isolation between concurrent threads.”；“No new interfaces are introduced.”

## 【2 相关代码】
- `marimo/_runtime/patches.py:182-200` `create_main_module`：把 `print_override` 用 `setdefault("print", ...)` 写进内核 `__main__` 的 `__dict__`，这就是 print 失去内建身份的根源。`patch_main_module` 在 `:216-227` 转调它。
- `marimo/_messaging/print_override.py:20-60` `print_override`：用 `functools.wraps(print)` 包了一层。
  - 当前线程 id 不在 `THREADS` 里时，转调 `_original_print`。
  - 在 `THREADS` 里时，取 `get_context().execution_context.cell_id`，经 `broadcast_notification` 发 `CellOutput.stdout`。
  - 它只处理 `sep` 和 `end`，忽略 `file` 和 `flush`。
- `marimo/_runtime/threads.py:23` 的 `THREADS: set[int]`：
  - `Thread.run`（`:145-169`）在 `:166` 把线程 id 加入，在 `:168` 移除。
  - 这里没有 try/finally，目标函数抛异常时 id 会残留，`teardown_context()` 也不会执行。
  - `Thread.__init__`（`:88-104`）给线程新建了 `KernelRuntimeContext`，其 stdout/stderr 为 None，并带一个 `redirect_console=False` 的新 stream。
- `marimo/_runtime/runtime.py:68` 导入 `print_override`，`:2542` 以 `print_override_fn=print_override` 传入。`marimo/_runtime/kernel_lifecycle.py:75,153-156` 把它转给 `patch_main_module`。
- `marimo/_runtime/redirect_streams.py:85-114`：
  - 编辑模式直接替换 `sys.stdout`/`sys.stderr`，并重定向 fd。
  - 运行模式用 `ThreadLocalStreamProxy`（`marimo/_messaging/thread_local_streams.py:32-98`），按线程分派。
  - `threads.py:91-92` 把线程上下文的 stdout/stderr 设为 None，所以线程内的 `sys.stdout` 写入仍走主 cell 的 stream，不会隔离。这就是当初需要 print_override 的原因。

## 【3 并列与牵连】
- 只有内核（编辑模式 `runtime.py:2542`）传入 `print_override`。`script_runner.py:88,123`、`kernel_runner.py:132`、`script_context.py:58`、`pyodide_session.py:481` 都传 None，不需要改。
- 如果改成“只在使用 `mo.Thread` 时才安装覆盖”，需要决定安装与卸载的时机，可选：
  - `Thread.__init__` 或 `run` 时把覆盖装到 `__main__` 或 builtins。
  - 或者改成线程感知的 `sys.stdout` 路由，不再替换 `print`。
- 牵连面：
  - 用户 cell 里的 `print`，以及 `from builtins import print`。
  - 多个会话（运行模式共享进程）。
  - `THREADS` 的全局状态。
  - `mo.redirect_stdout`（`capture.py:95`）。
  - `test_print_override.py` 里 patch 的 `_original_print` 符号。

## 【4 现有测试与约定】
- `tests/_messaging/test_print_override.py:18-196` 直接 import `print_override`，并 patch `marimo._messaging.print_override._original_print` 和 `...get_context`。
  - `:24`：`mock_print.assert_called_once_with("Hello, world!")`
  - `:76`：线程内断言 `mock_print.assert_not_called()`
  - `:83-89`：断言 `console.data == "Hello, world!\n"`
  - 这些测试依赖模块级名称。隐藏测试可能改了或删了它们，也可能保留这个接口。题面说“无新接口”，所以现有符号大概率要保留。
- `tests/_runtime/test_threads.py:107-140` `test_thread_print`：在 cell 里用 `mo.Thread`，线程内 `print("hello")`，断言：
  - 主 stream 没有 console 消息（`:135`）。
  - 线程 stream 有 2 个 operation（`:138`），首个 `console.data` 含 "hello"，channel 为 stdout（`:139-140`）。
  - 隐藏测试必然要求这条路由继续成立。
- 题面没有与现有测试冲突，只是要求“不用 Thread 时身份不变”。我没有找到现成的 numba 测试，也没有找到检查 `print is builtins.print` 的测试。

## 【5 边界与隐含要求】
- “不使用 mo.Thread”的判定时机：
  - 先建线程再 `start`，还是创建 `Thread` 对象时就算使用？
  - 覆盖装好后是否卸载？
  - 笔记本里先用过 Thread，之后 numba 编译的函数是否还能编译？
- 并发线程输出隔离：
  - 每个线程要按自己的 cell_id 和 context 路由。
  - 当前靠 `THREADS` 集合和线程 id，线程 id 可能复用。
  - `run` 缺 try/finally，异常会泄漏状态。
- `print` 的 `file=`、`flush=` 参数目前被丢弃。`sep=None` 或 `end=None` 会在 join 或拼接时出错（`kwargs.get` 返回 None）。
- cell 重跑、内核重启时的全局状态清理。
- 用户在 cell 里自己定义 `print` 的遮蔽情况（见 `runtime.py:214-230` 的 `unshadowed_builtins`）。
- 运行模式（多会话共享进程）和 Pyodide 路径。

## 【6 改动规模】
- 估计改 2–4 个文件：`patches.py`、`print_override.py`、`threads.py`，可能还有 `runtime.py` 或 `kernel_lifecycle.py` 的传参。
- 如果走“线程感知 stdout”路线，还会碰到 `redirect_streams.py` 或 `streams.py`，规模更大。
- 最小方案可以只在 `Thread` 首次创建时才把覆盖装进 `__main__`，属于局部修补。
- 完整方案需要处理安装、卸载、线程隔离，并要新增或调整测试，偏中等规模。

## 【7 难点一句话】
难点在于设计“按需安装、保持隔离”的机制：不用 Thread 时 `print` 必须是原生对象，用了 Thread 时又要按线程路由。这里没有复现脚本，隐藏测试的断言形式也无法确定，只能靠推断。