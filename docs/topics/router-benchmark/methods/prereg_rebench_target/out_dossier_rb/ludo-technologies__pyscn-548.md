【1 题面要点】
- 要求的行为：同一对代码片段的重复关系被报告成两个 clone group。两组的成员窗口只差一行（`with self.subTest(...)` 头行）。要求分组/去重阶段把这类互相重叠的组合并或抑制，使每个重复关系只报一次。
- 复现：Instagram/Fixit@bf8e1f5，pyscn v1.22.9，`pyscn analyze --json`。
  - 组 6：smoke.py 299-315 与 318-334，similarity 0.9692。
  - 组 14：298-315 与 317-334，similarity 0.9613。
  - 两组的结束行相同，起始行都相差一行。
- 期望输出（原句）："The clone-grouping/dedup stage should merge (or suppress) clone groups whose members are overlapping windows of the same underlying fragments, so each duplication relationship is reported once."
- 修法建议：没有给具体修法。只说是"merge (or suppress)"，以及不引入新接口（"No new interfaces are introduced"）。
- 另外提到 #416 已修，那次处理的是同一个组内的严格子集成员。本题是跨组的冗余。

【2 相关代码】
- `internal/analyzer/group_dedup.go:25` `dedupeStrictSubsetGroupMembers`：组内后处理。它对每个组调用 `filterMaximalPerFile`（:74）和 `covers`（:110），只处理同一文件内严格包含或完全相同的成员。
  - 它按组逐个处理（:39 循环），不比较不同组之间的关系。
  - 它还有 `refreshGroupMetadata`（:139）、`sortCloneGroups`（:164）和 `filterClonePairsWithSuppressedMembers`（:144）。
- `internal/analyzer/clone_detector.go:1120` `groupClonesWithStrategy`：唯一的调用点（:1125）。流程是 `strategy.GroupClones(pairs)`，然后 dedupe，再写入 `cd.cloneGroups`，并过滤 `clonePairs`。
  - 它被 `DetectClonesWithContext`（约 :641）和 `DetectClonesWithLSH`（约 :810）调用。
  - 服务层 `service/clone_service.go:162` 走 LSH 路径。
- `clone_detector.go:1139` `isOverlappingLocation`：只在配对阶段拒绝同文件内重叠的直接配对（:763、:1180）。
- 各分组策略的 `GroupClones`：`grouping_mode.go:41` 的 `NewConnectedGrouping` 是默认策略。另有 complete_linkage、centroid、k_core、star_medoid。

【3 并列与牵连】
- 新增的跨组去重应该放在 `groupClonesWithStrategy` 里，这样 `DetectClonesWithContext` 和 `DetectClonesWithLSH` 两条路径都能受益。
- 它不依赖具体的分组策略，所以五种策略都会经过这里。
- 牵连的地方：
  - `cd.clonePairs` 随组一起被过滤（见 `filterClonePairsWithSuppressedMembers`）。被合并掉的组所对应的 pair 要不要保留，需要决定。
  - 组的 ID 重新分配、`group.Similarity`、`CloneType`、`Size` 都要刷新。
  - 统计里的 `total_clone_groups` 和下游的重复率计算（service 层和 report）也会变。
  - 组 ID 在 JSON 里（id 6 和 14）。如果去重后重新编号，ID 会变，现有断言可能受影响。
- 我没有逐个确认 report 层的消费点。

【4 现有测试与约定】
- `internal/analyzer/group_dedup_test.go` 有 `dedupeGroups` 辅助函数（:18）和 `makeGroup`、`gf`。
  - `TestDedupe_AutofeatRepro`（:53）：`makeGroup(1, a, b, c)` 后期望 `out[0].Size != 2` 时失败。成员 512-542、515-542 和 548-575 里，515-542 被抑制。
  - `TestDedupe_EqualRangeKeepsFirst`（:78）、`TestDedupe_ChainCollapses`（:114）、`TestDedupe_DifferentFilesUntouched`（:135）、`TestDedupe_DisjointSameFileBothKept`（:164）。
  - `TestDedupe_EmptyAndNilGroups`（:178）、`TestDedupe_RecomputesMetadataAfterSuppression`（:194）。
  - `TestGroupClonesWithStrategy_FiltersSuppressedClonePairs`（:221）通过 `cd.groupClonesWithStrategy(NewConnectedGrouping(0.85))` 验证。`TestDedupe_E2EThroughConnectedGrouping`（:249）也是同类端到端测试。
- 隐藏测试很可能沿用这种风格：用 `makeGroup` 构造两个有重叠窗口的组，调用某个 dedupe 函数，断言只剩一个组。函数签名或名字未知，是风险点。
- 约定：保留最大窗口，相同范围保留先出现的，保证输出确定，并刷新元数据。
- 与题面不冲突，是对同一模式的延伸。
- 题面里保留哪个组没有说明。题面示例里 0.9692 的组 6 相似度更高，但窗口更小。

【5 边界与隐含要求】
- "重叠组"的判定条件没有定义：
  - 是否要求成员一一对应，即每个文件、每对成员都互相重叠？
  - 部分重叠的两个组是否也合并？
  - 重叠阈值（比如 IoU，或"包含"关系）是多少？
  - 阈值过松会把"相邻但不同"的克隆（比如相邻的两个测试块）误合并。
- 保留哪个：保留成员窗口更大的（组 14，298-315），还是保留相似度更高的（组 6）？这会影响隐藏测试的断言。
- 三个以上的组形成链状重叠时，是否传递合并。
- 组内成员数不同（比如一个组 2 个成员，另一个 3 个成员）时怎么处理。
- 跨文件的组：成员分布在多个文件时，要按文件配对比较。
- 合并后要刷新 `Size`、`Similarity`、`CloneType`，保持排序稳定。
- 要同步过滤或保留 `clonePairs`，以免 pair 数与组不一致。
- nil 组、空组、单成员组不能 panic。

【6 改动规模】
- 主要改 1 个文件（`group_dedup.go`），新增一个跨组去重函数，约几十行。
- `clone_detector.go:1125` 的调用处要小改，把它接入流程。
- 测试文件要补充。
- 这是局部修补，不需要新增结构，也不跨层。现有的 `groupDedupeResult`、`covers`、`refreshGroupMetadata` 可以复用。

【7 难点一句话】
难点不在代码量，而在判定语义：怎样定义"同一重复的两个窗口"（重叠度和成员对应关系），既能合并这对一行之差的组，又不把相邻但独立的克隆合并，并且选对保留哪个组，才能和隐藏测试的断言吻合。