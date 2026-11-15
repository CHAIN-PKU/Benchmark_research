## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) streamRangeHasTombstones() 在 first_id>max_deleted_entry_id 时早退返回无墓碑，导致 last_id 之后、first_id 之前的删除被漏判；2) streamReplyWithCGLag() 依赖该判断，nil 输出要联动检查；3) streamReplyWithRange() 里 entries_read++ 逻辑在读到 s->last_id 时应恢复为 entries_added，需先于自增分支处理；4) grep entries_read 的其他使用点（rdb.c 加载、XGROUP SETID、XCLAIM/XSETID、streamPropagateGroupID）确认主从/AOF/RDB 一致。
B. 删除在 last_id 之后但非末尾；删除的是末尾条目；删除在 last_id 之前或等于 last_id（lag 应仍有效）；全部删除/XTRIM；读到的条目恰为 last_id；COUNT 批量跨墓碑；entries_read 已为无效值的组。
C. src/stream.h 的 SCG_INVALID_ENTRIES_READ 注释和 streamEstimateDistanceFromFirstEverEntry 的函数说明需同步；tests/unit/type/stream-cgroups.tcl、stream.tcl 中现有 lag/entries-read/XDEL 用例的期望值要核对，新用例按同风格补；遵守文档约定（删除落在 last_id 与末尾之间 lag 为 nil，读到末尾后恢复计数、lag 为 0）。
D. 复现案例1全流程（nil → 读完 entries-read=4, lag=0）；复现案例2（只删0-3）；last_id 之前删除时 lag 仍为数值，且 DEBUG RELOAD 后 entries-read 与 lag 不变。
