【1 题面要点】
- 要求：`_thread.start_new_thread(fun, args[, kwargs])` 要返回新线程的 ID，现在返回 `None`。
- 题面给了用法示例：`thread_id = _thread.start_new_thread(my_thread_func, ())`，然后 `print("Thread ID:", thread_id)`。
- 题面没有给复现输出，没有给期望的具体值，也没有给修法建议。
- 题面只说了"性能和向后兼容要考虑"。
- 题面没有说返回的 ID 要和 `_thread.get_ident()` 一致，但 CPython 是一致的。

【2 相关代码】
- `py/modthread.c:222-275` `mod_thread_start_new_thread`：把参数打包进 `thread_entry_args_t`（147-155），调用 `mp_thread_create(thread_entry, th_args, &th_args->stack_size)`（271），最后 `return mp_const_none;`（273）。这是必改点。
- `py/modthread.c:131-134` `mod_thread_get_ident`：返回 `mp_obj_new_int_from_uint((uintptr_t)mp_thread_get_state())`。线程 ID 就是新线程栈上 `mp_state_thread_t ts` 的地址。
- `py/modthread.c:157-220` `thread_entry`：新线程入口。它在栈上声明 `ts`（162），再 `mp_thread_set_state(&ts)`（163）。
- `py/mpthread.h:43` `void mp_thread_create(void *(*entry)(void *), void *arg, size_t *stack_size);` 返回 `void`，是各 port 共用的接口声明。
- 各 port 的实现：
  - `ports/unix/mpthreadport.c:213-272`：用 pthread，`pthread_t id`，成功后把节点挂入链表。
  - `ports/rp2/mpthreadport.c:119-147`：只用 core1，返回 void。
  - `ports/stm32/mpthreadport.c:57-85`：`pyb_thread_new` 返回 `uint32_t id`，目前被丢弃。
  - `ports/esp32/mpthreadport.c:123-161`：`mp_thread_create_ex` 加 `mp_thread_create`，`th->id` 是 `TaskHandle_t`。
  - `ports/cc3200/mpthreadport.c:114-`：`xTaskCreateStatic` 返回 `TaskHandle_t`。
  - `ports/renesas-ra/mpthreadport.c:57`：和 stm32 类似。

【3 并列与牵连】
- 有 6 个 port 的 `mp_thread_create` 并列实现：unix、rp2、stm32、esp32、cc3200、renesas-ra。esp32 还有 `mp_thread_create_ex`。如果改了签名，这些都要同步改，否则其他 port 编译失败。
- `py/mpthread.h:43` 的声明也要同步。
- 我没有 grep 其他调用点，需要确认 `mp_thread_create` 是否还被别处调用。esp32 的 `mp_thread_create_ex` 没在 grep 结果里出现其他调用者，但我没有查 `ports/esp32` 以外的目录。
- 关键牵连：返回值要和 `get_ident()` 一致。`get_ident()` 返回的是线程栈上 `ts` 的地址，在 `thread_entry` 里才产生，创建线程的一方在 `mp_thread_create` 返回时拿不到。
  - 各 port 的 `th->id`（pthread_t、TaskHandle_t）和 `get_ident` 的值不同，直接返回它们会和 `get_ident()` 不一致。
  - 要保持一致，要么改 `get_ident` 的定义，要么让新线程把 `&ts` 回传给创建者（需要同步等待），要么让 `mp_thread_create` 返回一个 ID，同时 `get_ident` 也用同样的 ID。
- 没有 docs 引用：`docs` 下 grep `start_new_thread|get_ident` 无结果。我没有核对 `docs/library` 里有没有 `_thread` 文档。

【4 现有测试与约定】
- `tests/thread/thread_ident1.py:8-23`：线程里 `tid = _thread.get_ident()`，打印 `type(tid) == int, tid != 0, tid != tid_main`。主线程同理（`:16`）。没有 `.exp` 文件，输出对照 CPython。
- `tests/thread/thread_start1.py`：直接调用 `_thread.start_new_thread(thread_entry, ((i + 1) * 10,))`，不用返回值，不受影响。
- `tests/thread/` 下 `.exp` 文件只有 `stress_schedule`、`thread_exc2`、`thread_heap_lock`。其他测试用 CPython 的输出作对照，所以 CPython 行为是参考实现。
- CPython 行为：`start_new_thread` 返回的 ident 与线程里的 `get_ident()` 相同。隐藏测试很可能断言 `start_new_thread` 的返回值等于线程里 `get_ident()` 的值。
- 与题面不冲突，题面也说"similar to CPython"。

【5 边界与隐含要求】
- 返回值要和新线程里 `get_ident()` 的值相等。这是最可能的隐含要求。
- 返回值要是 `int`，非 0，且与主线程 ID 不同。
- 返回值要在线程启动前就确定，或者创建者要等线程设置好状态后才能拿到。
- 线程创建失败仍要抛 `OSError`（unix 的 `goto er`、rp2 的 "core1 in use"、stm32 的 "can't create thread"）。
- 线程快速结束时，返回的 ID 也要有效，不能读已释放的栈。
- GIL 和 GC 约束：`th_args` 的生命周期和 root 指针（`modthread.c:223-226` 的注释）。
- 多 port：unix 以外的 port 不能因为签名改动而编译失败。

【6 改动规模】
- 至少改 `py/modthread.c`（2 到 3 处）和 `py/mpthread.h`。
- 如果改 `mp_thread_create` 签名，还要改 6 个 port 的实现，约 7 到 8 个文件。
- 如果改让 `get_ident` 返回与平台线程 ID 一致的值，则涉及 `get_ident` 的实现，以及各 port 如何保存或获取这个 ID。
- 不用新增模块或数据结构，但要在公共层和 port 层之间贯穿一个新的返回值。
- 可能最小的做法：只改 unix 之类的主要 port，但会破坏其他 port 编译，不可取。

【7 难点一句话】
`get_ident()` 返回的是新线程栈上 `ts` 的地址，创建者在 `mp_thread_create` 返回时拿不到它。要让 `start_new_thread` 的返回值和线程里的 `get_ident()` 一致，要么改 ID 的定义，要么做线程间同步，还要把改动同步到所有 port。