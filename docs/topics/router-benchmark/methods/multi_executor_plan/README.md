# 多执行者跑题计划（2026-11-16 20:40，crc 20:31 要求）

crc：其他执行者不必跑全部；只跑「比较容易错的一部分 + 一部分对的」，共约 150 道；便宜题优先；服务器已有的 GLM / Opus 等历史记录直接复用，只补没跑够或没跑过的；版本管理与记录管理要做好。

## 选题（150 道）
1. **旧题 92 道**（old_selection.csv，role=selected）：DS 全部 46 道挂题 + 每道挂题配一道同仓库的 DS 做对的题（46 道）。同仓库配对，方便比较执行者间的差异；种子 20261116，可复现。
2. **rebench 58 道**：DS 至少挂一次的全部（约 23 道）+ 同数量级 DS 做对的题（约 35 道，按语言分层抽）。这一步由 DSH 按 DS 标签选（我不看 rebench 标签），选出后把题号清单提交到本目录 `rebench_selection.csv` 并记 sha256。
3. 备选（reserve，30 道）：某题太贵（单题 >40 分钟）或环境有问题时，用同仓库备选替换，替换要记在 ledger。
4. 执行者：GLM-5.3 flashX、Sonnet 5.5、Haiku 5.5、Kimi K3.1 Pro；已有 Opus / Fable 记录的题直接复用。

## 复用规则（不浪费）
- 先盘点：对 150 题 × 执行者，列出服务器已有的有效运行（环境错误、预算截断、守卫全挂的不算）；每题 ≥1 次有效运行即可复用，补不足的。
- 评分环境必须与 DS 一致（便宜与强模型评分环境一致，见 AGENTS.md 第 3 条）；口径：至少一次通过算过，同时保留 n_runs/n_pass。

## 记录管理（ledger）
- `runs_ledger.csv`（模板见本目录）：每行一次「题 × 执行者」的结果，字段：task, executor, source(reused/new), n_runs, n_pass, job_dir, start_epoch, end_epoch, cost_usd, valid(1/0), note。DSH 追加，不改旧行；复用的行写来源路径。
- 清单与脚本一事一个 commit；ledger 每批追加一次提交；sha256 记入 README。
- 凭据不入库；题面/快照不含标准答案和隐藏测试。

## 估算成本（新增运行，单遍）
Sonnet 约 $0.22/题、Haiku $0.039/题、GLM $0.048/题；150 题 × 3 个执行者约 $46；Kimi 待验证后再报。复用越多越省。

## 复用盘点（11-16 20:50，crc 20:38/20:40 要求；服务器 raw_runs/taxonomy，与 ai-market 仓库 data/cold_start/taxonomy 为同一批）
来源：早先「claw」线跑的真实仓库题，每个文件含 resolved / passed / leak_verdict 等。有效 = agent_ok、patch_applied、未污染、未被杀、resolved 明确。明细见 reuse_inventory.csv（只含题号、模型、结果、花费、来源文件名，无凭据、无标准答案）。
| 模型 | 有效题数 | 在我们 186 道旧题里 | 在选定的 92 道里 |
|---|---|---|---|
| GLM-5.3 flashx | 66 | 57 | 27 |
| Fable 5.1 | 54 | 49 | 25 |
| Opus 5 | 42 | 37 | 20 |
| Kimi K3.1 Pro | 35 | 32 | 18 |
| Mimo v2.6 Pro | 28 | 25 | 15 |
一致性检查：这条线里 DS 的有效记录与我们 DS 标签一致 60/68（88%），评分环境基本可比；不一致的 8 道需逐题看原因后再决定是否复用。Haiku、Sonnet 没有任何记录，需要新跑。
