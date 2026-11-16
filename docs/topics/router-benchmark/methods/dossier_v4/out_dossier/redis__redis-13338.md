我已经查证完毕，下面是档案。

# 仓库档案：XINFO lag 在 XDEL 后错误（redis 7.2.x）

## 【1 题面要点】
- 要求的行为：
  - 当 group 的 last-delivered-id 与 stream 的 last-id 之间有条目被 XDEL 或 trim 删除时，`lag` 应返回 nil。
  - 之后 group 读到流末尾，`entries-read` 应修正为 `entries-added`（案例中为 4），`lag` 为 0。
- 题面给了两个完整复现。
  - 案例 1：先 XDEL 0-1、0-2，再 XDEL 0-3。lag 仍为 2，应为 nil。再读完后 entries-read=3、lag=1，应为 4 和 0。
  - 案例 2：只 XDEL 0-3。lag 为 nil 是对的，但读完 0-4 后 entries-read=3、lag=1，应为 4 和 0。
- 题面没有给修法建议，也没有指出出错的函数。
- 依据的是文档原句：“One or more entries between the group's last-delivered-id and the stream's last-generated-id were deleted … the returned value is set to NULL”。另一句是 “Once the consumer group delivers the last message … it will be set with the correct logical read counter”。

## 【2 相关代码】（均在 `src/t_stream.c`）
- `streamRangeHasTombstones`，1400–1436：判断 [start,end] 内是否有墓碑。
  - 1408 行：`first_id > max_deleted_entry_id` 时直接返回 0，注释是“最新墓碑在第一个条目之前”。
  - 这是我推断的根因：案例 1 中 first_id=0-4，max_deleted=0-3，被判无墓碑。但 0-3 位于 group.last_id(0-2) 与 0-4 之间，其实应判有墓碑。
  - 1427 行是区间比较：`start<=max_deleted<=end`。
  - 只用 `max_deleted_entry_id` 这一个标量，无法区分“已被 trim 掉的老墓碑”和“夹在 group 位置与 first_id 之间的墓碑”。
- `streamReplyWithCGLag`，1441–1469：lag 的计算。
  - 1449 行：`entries_read` 有效且 `!streamRangeHasTombstones(...)` 时，`lag = entries_added - entries_read`。
  - 否则走 1456 行的 `streamEstimateDistanceFromFirstEverEntry`；返回无效值时回复 nil。
- `streamEstimateDistanceFromFirstEverEntry`，1493–1530：估算某 ID 的逻辑读计数。
  - 1516 行：`max_deleted==0 || max_deleted < first_id` 时视为“无碎片”。
  - 1518 行：`id < first_id` 时返回 `entries_added - length`。
  - 案例 1 中 id=0-2 < first=0-4，且 max_deleted=0-3 < first，于是返回 3，把已删除的 0-3 也当成已读，口径有问题。
  - 同一个 `max_deleted < first_id` 的判断在这里重复出现。
- `streamReplyWithRange`，1686–1695：XREADGROUP 推进 group 时更新 `entries_read`。
  - 1687 行：`entries_read` 有效且 `!streamRangeHasTombstones(s,&id,NULL)` 时 `entries_read++`。
  - 否则在 1694 行用 estimate 重算。
  - 案例中读 0-4 时 id=0-4 即 last_id，`streamRangeHasTombstones` 为假（first_id=0-4 > 0-3），于是在 entries_read=2 上 +1 得到 3。
  - 案例 2 中 entries_read=2 有效，但 0-3 被删后 0-4 仍被 ++，得到 3。这解释了“读完后 entries-read=3”。
- `xdelCommand`，3546–3570：更新 `max_deleted_entry_id`（3555 行）和 `first_id`。
- 其他读写 `entries_read` 的位置：
  - `rdb.c:2936` 老版本 RDB 加载时调用 estimate。
  - `t_stream.c:3742`、3938 行是 XINFO 输出。
  - `t_stream.c:2702`、`aof.c:2158`、`rdb.c:1123` 是 SETID、持久化相关。

## 【3 并列与牵连】
- 关键判断“墓碑是否在 group 之后”同时出现在三处，行为必须一致：
  - `streamRangeHasTombstones`（1408 行）。
  - estimate 里的 1516 行条件。
  - XREADGROUP 的 1687 行。
- 调用点：
  - `streamReplyWithCGLag` 调用 `streamRangeHasTombstones`（XINFO GROUPS 和 XINFO STREAM FULL 都会用到，见 3742、3938 附近输出）。
  - `streamReplyWithRange` 调用它。
  - `rdb.c:2936` 调用 estimate。
  - XCLAIM/XGROUP SETID 通过 `entries_read` 传播，涉及主从一致性（1581 行注释提到）。
- 牵连：改 `streamRangeHasTombstones` 的语义会同时影响 lag 与 `entries_read` 计数。必须同时保证既有“XDEL 后再读”和“XTRIM”测试仍通过。

## 【4 现有测试与约定】
- `tests/unit/type/stream-cgroups.tcl`，“Consumer group lag with XDELs”（1177–1240）：
  - 先 XDEL 3-0，group 从 0 开始，读 1、2、4 的过程中 `entries-read {}` 且 `lag {}`（1190–1209 行）。
  - 读到 5-0 后 `entries-read 5`、`lag 0`（1214–1215 行）。
  - 再 XADD 6-0 后 lag 1（1221 行）。
  - `XTRIM MINID = 3-0` 后，g1 为 `entries-read 5`、`lag 1`；g2 为 `entries-read {}`、`lag 3`（1226–1230 行）。
  - `XTRIM MINID = 5-0` 后，g2 lag 2（1239 行）。
  - 这些测试依赖“墓碑在 first_id 之前就不算碎片”的快速路径。trim 不更新 `max_deleted`，但 XDEL 会更新，所以不能简单去掉 1408 行的判断。
  - 注意：g2 在 XTRIM 后 `entries-read {}`，lag 却是 3，是靠 estimate 算出来的。
- 其他测试：
  - sanity 测试（1144–1174）：`entries-read 5` 且 `lag 0`，随后 `lag 1`。
  - 1374–1392：XREADGROUP ACK 传播 `entries-read 3`、`lag 0`。
  - 空流测试（1122–1141）：lag 0。
  - 老版本 RDB 加载测试（1242 起）：`entries-read 1`，`lag 1`；g2 为 0 和 2。
- 约定与规范：`streamEstimateDistanceFromFirstEverEntry` 顶部注释（1471–1492）和 `stream.h:59` 的注释描述了语义；docs 的 XINFO-GROUPS 说明与题面一致。
- 与题面不冲突，题面期望与文档一致。仓库里没有现成的、能直接对照的测试覆盖“XDEL 掉 last-delivered 与 first_id 之间的条目”这一情形。

## 【5 边界与隐含要求】
- 已删条目恰为 stream 最后一项的情形：案例 2 的 0-3 在中间，案例 1 的 0-3 在 0-4 之前。需要兼顾 `max_deleted < first_id` 但墓碑夹在 group 位置与 first_id 之间。
- 在 group 位置之前或在 first_id 之前被删除的墓碑，不应使 lag 变 nil，需避免误判。
- 读到最后一个条目时，应在无有效墓碑前提下得到 `entries_added`，即让 `entries_read` 重新变得有效。具体是 id==last_id 时返回 `entries_added`，这点 estimate 在 1506 行已经处理。
- 被 XDEL 删到流为空、或 XTRIM 与 XDEL 混用。
- XSETID 可以直接设置 `max_deleted_entry_id`（2810 行），RDB 加载也会设置，行为要保持一致。
- 主从 / AOF 重写后 `entries_read` 的一致性，不能破坏 XCLAIM LASTID 的传播。
- 不能让既有 XTRIM 测试（g2 lag 3、2）回归。

## 【6 改动规模】
- 以 `src/t_stream.c` 为主，预计 1–3 处局部判断修改：
  - `streamRangeHasTombstones`。
  - 可能还有 estimate 的 1516 行条件，以及 1687 行的计数逻辑。
- 另需在 `tests/unit/type/stream-cgroups.tcl` 增加回归测试。
- 属于局部修补，不需要新增结构。如果想用“精确的墓碑位置”而不是单个 `max_deleted`，才会要新增字段并改 RDB/AOF，那样规模会大很多，但仓库现有设计看起来不走这条路。

## 【7 难点一句话】
难点在于把“墓碑是否位于 group 位置之后”的判断修对，同时不破坏 XTRIM 等已有快速路径：根因是 `first_id > max_deleted_entry_id` 这个捷径，会把夹在 group 的 last_id 与 first_id 之间的墓碑漏掉。这个判断分散在三处，需要一致修改。