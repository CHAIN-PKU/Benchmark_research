## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 其他可能需要一并处理的位置
- `src/cluster_legacy.c` 的 `addShardReplyForClusterShards`（约 5666 行）：它取 `listFirst(nodes)` 作为代表节点，再用 `clusterNodeGetPrimary` 取槽位信息。请核对这个“第一个节点”是否一定是现在持有槽位的节点。示例第 3 个分片里有两个 role 为 master 的节点，其中一个是 fail 状态的旧主。请弄清旧主和刚提升的副本在 `server.cluster->shards` 的节点列表里排在什么顺序，以及它们的 `slot_info_pairs` 分别是什么状态。
- `clusterGenNodesSlotsInfo`（约 5392 行）：它只给 `server.cluster->slots[]` 当前指向的节点填充 `slot_info_pairs`。槽位已经转给新主时，旧主不会有任何槽位信息。请对照这一点，检查上一条里选出的节点是不是拿不到槽位。
- 同一个分片的节点列表在其他地方也有使用，可以一并检查这些地方对“谁是主”的判断是否一致：`src/cluster.c` 里的 `CLUSTER SLOTS` 路径（约 1266–1350 行）；`src/cluster_legacy.c` 里加入、移除分片节点的函数，以及 `clusterNodeGetPrimary`。
- `addShardReplyForClusterShards` 循环里每个节点都会调用 `clusterFreeNodesSlotsInfo`。改动选主逻辑后，请确认槽位信息的释放时机依然正确，没有泄漏，也没有提前释放。

B. 可能被检查的输入和边界情况
- 主节点宕机后，副本通过故障转移（failover）晋升，旧主仍被标记为 fail 并留在同一个分片里。此时槽位应该显示在这个分片下。
- 副本晋升后，旧主重新上线并变成副本。
- 一个分片里只有一个节点，且该节点没有槽位，比如新加入的空主节点。此时仍应返回空数组。
- 分片内有多个节点都带 master 标志，或者节点列表里的顺序和“主在前”的假设相反。
- 分片里存在 handshake 状态的节点，或者 `CLUSTER_NODE_NOADDR` 之类的特殊节点。

C. 仓库里已有的约定、文档和测试
- `src/commands/cluster-shards.json` 以及同目录下的说明文档：核对 `slots` 字段的语义，也就是该分片当前拥有的槽位。
- `tests/unit/cluster/` 下已有的 CLUSTER SHARDS 相关用例，例如 `shardid`、`cluster-response-tls`、`links` 等。请搜索 `cluster shards` 或 `CLUSTER SHARDS`，了解测试的写法，以及它们是否隐含了“第一个节点就是主”的假设。
- `tests/support/cluster_util.tcl`：先看里面有没有辅助函数可以用来构造 failover 或停止节点的场景，再决定怎么写测试。
- 检查 `src/cluster_legacy.c` 里 `CLUSTER NODES` 对失败节点的处理，对照 `clusterGenNodesSlotsInfo(filter)` 的 filter 约定。

D. 提交前建议额外自测的情况
1. 搭建 3 主 3 从的集群，停掉一个主节点。等待故障转移完成后，在其他节点上执行 `CLUSTER SHARDS`，确认该分片的 slots 非空，且与 `CLUSTER SLOTS` 一致。
2. 在故障转移完成之前、旧主刚被标记为 fail 时执行 `CLUSTER SHARDS`。同时覆盖旧主恢复并成为副本之后的情况。
3. 确认没有槽位的空主节点的分片仍返回空数组，并确认各分片的槽位范围互不重复，且合计覆盖 16384 个槽。
