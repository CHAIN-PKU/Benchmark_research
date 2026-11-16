# 档案：out_forward 在 `require_ack_response` 下关停时的竞态

**说明**：我没有跑任何测试或复现。下面第 2 到 5 节里的竞态机制是读代码推断的，没有验证。

## 【1 题面要点】
- 要求的行为：停止 fluentd（`td-agent`）时，`out_forward` 在 `require_ack_response true` 下不再抛出 ack_handler.rb 里的异常。期望输出原文是 "No error."
- 三种报错：
  - `unexpected error while receiving ack error_class=IOError error="closed stream"`
  - `unexpected error while receiving ack message ... "stream closed in another thread"`
  - `NoMethodError undefined method 'disable!' for nil:NilClass`
- 复现：只写了"开启 require_ack_response，在活跃传输时停止 Fluentd"。没有脚本、没有期望日志。
- 修法建议：没有。唯一的诊断是 "shutdown sequence is racy i.e. multiple threads can process the same ack message concurrently"。
- 题面没有给 API 或接口约束。隐藏测试可能测 AckHandler 或 out_forward 的关停流程。

## 【2 相关代码】
- `lib/fluent/plugin/out_forward.rb:303-306`，`start`：开了 ack 就起线程 `:out_forward_receiving_ack`，执行 `ack_reader`。
- `out_forward.rb:508-514`，`ack_reader`：`while thread_current_running?` 循环调用 `ack_check`。
- `out_forward.rb:516-536`，`ack_check`：调用 `@ack_handler.collect_response`。块内先 `@connection_manager.close(sock)`，再按结果处理：
  - SUCCESS 走 `commit_write`。
  - FAILED 走 `node.disable!` 加 `rollback_write`。
  - CHUNKID_UNMATCHED 走 `rollback_write`。
  - 其他值：`log.warn("BUG: ...")`，有 `chunk_id` 时再 `rollback_write`。
- `out_forward.rb:333-349`，`stop` 和 `after_shutdown`：
  - `stop` 只做 `@connection_manager.stop`，在 keepalive 时清空 socket cache。
  - `before_shutdown` 把 `@suspend_flush` 设为 true。
  - `after_shutdown` 在主线程调用 `last_ack`。
- `out_forward.rb:356-359`，`last_ack`：再调一次 `ack_check`，在关停线程里同步收尾 ack。
- `lib/fluent/plugin/out_forward/ack_handler.rb:40-80`，`collect_response`：
  - 加锁整理 `@ack_waitings`，过期的判为 FAILED。
  - 对剩余 socket 做 `IO.select`。
  - 逐个调用 `read_ack_from_sock`，最后 yield。
  - 外层 `rescue => e` 记录 "unexpected error while receiving ack"，即 case 1。
- `ack_handler.rb:107-142`，`read_ack_from_sock`：
  - 读 socket。
  - `find(sock)`，返回 `nil` 即 `info` 为 nil。
  - 之后 `info.node.host` 和 `info.chunk_id` 会触发 NoMethodError。
  - 外层 `rescue` 记录 "...ack message"，即 case 2。返回 `[nil, FAILED]`。
  - `ensure delete(info)`。
- `ack_handler.rb:148-158`，`find` 和 `delete`：各自单独加锁。"find 与 delete 之间不是原子操作"是推断的竞态点。
- `ack_handler.rb:69-75`：`info.nil?` 时 yield `nil, nil, nil, ret`。随后 `ack_check` 里的 `node.disable!`（line 524）在 node 为 nil 时抛 NoMethodError，即 case 3。注意这发生在 yield 块里，被 `collect_response` 外层 `rescue` 吞掉并记为 error。

**推断的竞态路径**：线程 `stop` 只把 running 置 false（`lib/fluent/plugin_helper/thread.rb:124-138`），不 join。join 要等 `close`（line 153）。所以 `after_shutdown` 里主线程的 `last_ack` 与 ack_reader 线程可能同时在 `collect_response`。两边对同一 sock 都 `find` 到同一 info 并读取，一方先 `delete` 或关闭 socket，另一方就读到 closed stream 或 `find` 为 nil。

## 【3 并列与牵连】
- 两条调用路径：线程里的 `ack_reader` 和 `after_shutdown` 的 `last_ack`，都走 `ack_check`。修复大概要保证两者不并发。可选方向：
  - 关停时先 join ack 线程再 `last_ack`。
  - 给 `ack_check` 或 `collect_response` 整体加锁。
  - 让读取与 delete 原子化。
- `@connection_manager.close(sock)`（`connection_manager.rb:72-79`）：
  - keepalive 时 `checkin` 到 socket cache，否则 `close_write` 加 `close`。
  - 它在 yield 块里被调用，与读取方的 socket 生命周期交织。
  - `stop` 里 `@connection_manager.stop` 会 `socket_cache.clear`，可能关掉还在等 ack 的 socket。
- `connection_manager.rb:57, 103`：`ack.enqueue(socket)` 是写入侧，与读取侧共用 `@mutex`，改锁时要考虑。
- `Output#after_shutdown` 里的 `try_rollback_all`（`output.rb:555`）在 `last_ack` 之后（`out_forward.rb:347-348`）。
- `ack_handler.rb:120` 有被注释掉的 `# info.node.disable!`。
- 影响面：`NoneHeartbeatNode` 和 `Node` 共用同一个 `@ack_handler`（`out_forward.rb:457-459`）。`test_out_forward.rb:667` 用 `mock.proxy(...).read_ack_from_sock`，所以如果重命名或移走这个私有方法，该测试会受影响。

## 【4 现有测试与约定】
- `test/plugin/out_forward/test_ack_handler.rb`：
  - line 10-12 的 data 参数化：
    - SUCCESS 对应匹配的 ack。
    - CHUNKID_UNMATCHED 对应 `'unmatched'`。
    - FAILED 对应空串。
  - line 29-37 断言 `a1 == chunk_id, a2 == node, a3 == r, a4 == state`。
  - line 63-66，"returns nil if raise an error"：`recv` 抛错时断言 `a1`、`a2`、`a3` 为 nil、`a4` 为 FAILED。这个行为约定会与"修复 nil node"相互牵连。修复后若改变此约定，这条测试可能需要同步改。
  - line 92-95："when ack is expired" 断言 yield 了 `chunk_id`、`node`、`r`，结果 FAILED，且 `recv` 从不被调用（line 83）。
- `test/plugin/test_out_forward.rb`：
  - line 667-698 的关停 ack 测试，在 `d.instance.stop`、`before_shutdown`、`shutdown`、`after_shutdown` 流程下断言 `!nacked`、`acked_chunk_ids.size == 1`。它是最接近的现有测试，隐藏测试大概率在此扩展，或在 `test_ack_handler.rb` 加一个并发或 "socket 已被关闭" 的用例。
  - line 386-402 断言 `@suspend_flush` 的开关。
- `AckHandler` 的现有单测没有覆盖并发。
- 仓库里没有外部规范决定这个行为。Forward Protocol 只规定 ack 内容，不规定关停顺序。
- 与题面的冲突：目前没有发现。

## 【5 边界与隐含要求】
- `find(sock)` 返回 nil 时要处理，不能再解引用。注意 `ensure delete(info)` 对 nil 的行为。
- 空闲且有未发完的 ack 时，`last_ack` 仍应尽量收到并提交，不能为了不报错而丢 ack。
- 关停时 ack 读取线程可能阻塞在 `IO.select`（间隔最长 1 秒）。若改成 join，要保证不卡住关停。
- 非 keepalive 与 keepalive 两种模式，socket 关闭方式不同（`close` 与 `checkin`）。
- TLS socket 使用 `readpartial`，非 TLS 使用 `recv`，两者在 socket 被关闭时抛的异常不同（`IOError` 与其他）。要考虑是否需要 rescue `IOError`。
- 正常的 nil 路径要避免 `node.disable!` 作用在 nil 上（`out_forward.rb:524`）。
- 避免死锁：`@mutex` 在 `find`、`delete`、`enqueue`、`collect_response` 里不可重入，加大范围的锁时注意别在持锁时 yield。
- 不应把正常关停的预期情况记成 error 日志，否则题面的 "No error" 仍不满足。具体判据是我对题面的理解，隐藏测试怎么判不确定。

## 【6 改动规模】
- 预计 1 到 2 个文件、几处小改：`ack_handler.rb`（`read_ack_from_sock`、`find`、`delete` 一带），可能加上 `out_forward.rb`（关停顺序或 `ack_check`）。
- 属于局部修补，不需要新增结构，也不贯穿多层。
- 测试可能新增 1 个用例。

## 【7 难点一句话】
难在从题面只有"关停有竞态"这一句描述，自己定位并发路径：`after_shutdown` 的 `last_ack` 与仍在运行的 ack 线程如何交错。同时要选对修法（串行化、原子化 find 加 delete，或先停线程），既不破坏现有 `test_ack_handler.rb` 里 nil 结果的约定，也不丢 ack。这个并发场景又难以稳定复现，隐藏测试具体断言什么也无从得知。