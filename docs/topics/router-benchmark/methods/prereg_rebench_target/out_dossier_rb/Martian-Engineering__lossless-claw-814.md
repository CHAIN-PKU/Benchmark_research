# 仓库档案：isolated cron 复用稳定 sessionKey 导致上下文串用

## 【1 题面要点】
- 要求的行为：不同的 isolated cron 运行时会话（runtime sessionId 不同）复用同一个稳定 sessionKey 时，不能共享活跃的 LCM 上下文。
- 三条保持不变的约束：
  - 前几次运行的数据仍然归档保留。
  - 同一次运行内部的 compaction 仍然正常。
  - 普通非 cron 会话的连续性不变。
- 题面没有复现步骤、期望输出或修法建议。
- 关键句只有一句："No new public interfaces are introduced."
- 题面没有说怎么识别“isolated cron”。
- 仓库里 cron 的 key 形态有两种：`agent:main:cron:nightly` 和 `agent:main:cron:nightly:run:run-123`。后者见 test/session-patterns.test.ts:15-16、README.md:325。

## 【2 相关代码】
- `src/store/conversation-store.ts:393` `getConversationBySessionKey`：只按 `session_key=? AND active=1` 取最新一行，不看 sessionId。这是串用的根源。
- `src/store/conversation-store.ts:488-529` `getOrCreateConversation`：
  - 按 key 命中后，如果 sessionId 不同，就直接 `UPDATE session_id`，把旧会话重新挂到新运行时上（第 495-505 行）。
  - 这就是“复用活跃上下文”的直接来源，bootstrap 走这里（engine.ts:7183）。
- `src/store/conversation-store.ts:449` `getConversationForSession`：assemble、afterTurn 等先按 key 再按 sessionId 查找，同样会命中旧会话。
- `src/engine.ts:6917` `rotateStaleSessionKeyConversationIfTrackedTranscriptMissing`：
  - 仅当旧 transcript 文件已不存在时才轮转。
  - 轮转通过 `applySessionReplacement`（engine.ts:9397）完成：归档旧会话，必要时新建替换行。
- `src/engine.ts:6976` `findAmbiguousSessionKeyRuntimeRollover`：
  - 旧 transcript 仍存在且 sessionId 不同时，返回“歧义换代”。
  - bootstrap（7149-7181）和 afterTurn（6699-6733）在没有 frontier anchor 时 fail closed。
  - assemble（8796-8809）回退到 live messages。
  - 对 cron 来说，这个守卫要么阻止导入，要么继续用旧会话，都不对。
- 调用点：
  - engine.ts:6418 afterTurn 对账。
  - engine.ts:7143 和 7150 bootstrap。
  - engine.ts:8772 和 8797 assemble。
- `src/engine.ts:9447-9540` `handleBeforeReset` 和 `handleSessionEnd`：生命周期的归档入口。
- 识别 cron 可以复用 `src/session-patterns.ts` 的 glob，或判断 key 中是否含 `:cron:`。engine 里已有 `isStatelessSession` 和 `shouldIgnoreSession` 这类 key 判断，可作参考。

## 【3 并列与牵连】
- 三个阶段（bootstrap、assemble、afterTurn）各自调用 rotate 和 ambiguous 两个守卫。修复要在 bootstrap、afterTurn、assemble 三处都生效，否则会有一处仍然串用。
- 存储层的 `getOrCreateConversation` 的“按 key 重挂 sessionId”分支是第二个相关位置。
  - 如果只在 engine 层归档旧会话，这里就会找不到活跃行，转而新建，行为正确。
  - 如果漏掉某个阶段，这里仍会把旧会话改挂到新 sessionId 上。
- `getConversationFamilyIds`（conversation-store.ts:408）按 sessionKey 聚合所有历史会话，包括归档的。
  - 它可能让检索和 expand 把旧 cron 运行的内容当作同一家族。
  - 这与“归档但保留”一致，但需要确认没有被意外当作活跃上下文。
- 会影响的地方：
  - lcm-doctor-cleaners 的 `cron_sessions` 用 `LIKE 'agent:main:cron:%'`。每次运行产生新行会增加清理对象，但不冲突。
  - README 里忽略 cron 的配置同样适用。
- 这一路径也被 session-queue 的 key（`resolveSessionQueueKey`）和 `lastFullReadFileState` 等缓存牵涉。

## 【4 现有测试与约定】
- test/engine.test.ts:11284 和 11360（"bootstrap fails closed on ambiguous runtime rollover while the old transcript still exists"）：
  - 断言 `reason: "ambiguous session-key runtime rollover"`，日志含该字样。
  - 用的 key 是 `agent:main:test:...`，不是 cron，所以应保持不变。
- test/engine.test.ts:11463：assemble 在歧义换代时回退到 live messages。
- test/engine.test.ts:1555：idle rollover 归档旧行并新建。
- test/engine.test.ts:434：`ignoredSessionKey = "agent:main:cron:nightly:run:run-123"`，是忽略模式测试。
- 隐藏测试很可能：
  - 用 cron key，换 sessionId 和 sessionFile，断言新的 bootstrap 生成新的 conversationId、旧行 `active=0`。
  - 同时断言非 cron key 的行为不变。
- 与题面不冲突，但新行为（cron 不再 fail closed）与上述歧义守卫在 cron key 上互斥，需要按 key 分流。
- 约定：AGENTS.md 未细读，但仓库有 specs、architecture 目录可能说明会话生命周期。cron 的 key 形态以 README:325 为准。

## 【5 边界与隐含要求】
- 判定“isolated cron”的依据：key 含 `:cron:`，还是只认 `:run:`？
  - 题面说“stable session key”，所以 key 可能是 `agent:main:cron:nightly` 且没有 `:run:`。
  - 是否应只在 sessionId 变化时才轮转？
- 同一次运行内（sessionId 相同）不能轮转。afterTurn、assemble 每轮都会调用，必须靠 sessionId 比对避免每轮归档。
- 旧运行的 transcript 文件可能仍在（触发 ambiguous 分支），也可能已被清理（触发 rotate 分支）。两种情况都要得到新会话。
- 轮转要在 session queue 和事务内做，避免并发 bootstrap 和 afterTurn 竞态创建两个活跃行。
  - `createConversation` 有 UNIQUE 冲突兜底，回退到 `getConversationBySessionKey`。
  - 兜底可能返回旧行，需要检查。
- 同一 sessionId 的 afterTurn 先于 bootstrap 到达时，要能建出会话。
- `applySessionReplacement` 的 `isFreshLifecycleConversation` 空会话 no-op 判断可能影响“已是新鲜行”的情形。
- 轮转后 bootstrap 状态、`lastFullReadFileState` 等缓存要对新会话干净。
- compaction 在当前运行内必须仍然作用于新活跃行。
- 归档后的旧摘要不应被 assemble 拉进新会话。

## 【6 改动规模】
- 估计改 1-2 个文件：`src/engine.ts` 为主，可能加 `conversation-store.ts` 的小改动。
- 涉及 3-4 处：
  - 新增一个 cron 识别辅助函数。
  - 在 rotate 和 ambiguous 守卫里对 cron key 分流为“归档并换代”。
  - 可能还要改 `getOrCreateConversation` 的重挂分支。
- 局部修补，不需要新增结构或公共接口，但要贯穿 bootstrap、afterTurn、assemble 三个阶段。
- 测试需要新增，约 3 个用例。

## 【7 难点一句话】
难点在于守卫分散在 bootstrap、afterTurn、assemble 三处，且旧 transcript 是否存在会走不同分支，要让 cron key 在所有分支下统一轮转，同时保证同一运行内不重复归档、非 cron 的 fail-closed 行为不变。

（注：我没有读 AGENTS.md、specs/、architecture/，也没有确认宿主实际传给 engine 的 cron sessionKey 是否带 `:run:` 后缀。这两点需要在后续核实。）