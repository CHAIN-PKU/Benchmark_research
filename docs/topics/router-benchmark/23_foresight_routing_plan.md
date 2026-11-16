# Capability Foresight：论文结构最小修改 + Routing 应用实验方案（2026-11-16 晚）

原则（crc 16:42）：Benchmark first, routing as evidence, not as the paper's identity。不打断正在跑的执行，不改已冻结的预测、测试集和预注册方案。

## 1. 对 v6 结构的最小修改
两条主线并列，五步骨架不变：
- **主线 A：Foresight 作为 Benchmark**（第 3–5 章）：测量协议、谁判得准、为什么有差异（执行 vs 预测分离；风险识别 vs 风险权衡）。
- **主线 B：Foresight 预测方法**（第 6 章）：在同等或更低预算下，「查证档案 + 判断」的工作流能否比直接判断、统计基线更准，且概率可比、可校准。
- 第 7 章「有什么用」中，任务分配升级为 **Downstream Decision Utility：Agent Routing**（离线反事实 + 小规模端到端）；数据筛选、题目筛选保持离线证据。
- Related Work 按建议措辞：Rather than proposing another routing algorithm, we investigate the task-specific capability foresight underlying many agentic decisions…；不写「所有路由本质都是预测成功率」，不写「外部路由器无法利用中间上下文」，同信息条件下比较。

## 2. 现有资产审计（可复用 / 要新增）
| 类别 | 已有 | 状态 |
|---|---|---|
| 简单统计基线 | 仓库历史挂率、相似题 kNN、简单特征、事前知识点（stack_exp.py）；自身历史在 14 家上复核（public_difficulty/） | 可复用，旧题 |
| 题目难度估计 | 只看题面的 12 条特征（issue_cues/，0.57）；公开难度（14 家，事前不可得，仅作上限） | 可复用 |
| Agent 历史表现 | 各 Agent 整体通过率（DS 79%；公开 14 家 39%–76%） | 现成 |
| 直接判断 | 前瞻 123：Sonnet/Opus/Haiku 通用组、s2/s3、结构化、模拟；rebench 100：Sonnet 通用组 | 已冻结 |
| 两阶段工作流 | 换线索、同线索五家（same_evidence_judges/）；规则（prereg 77）；经验卡 E0–E3（prereg 60）；仓库档案 v4（dossier_v4/，旧题 157 份） | 前两项已冻结待揭晓；v4 扩样本进行中 |
| Agent-specific | 带做题者身份 DS/GLM（prereg 77）；历史经验 hist_v1（前瞻） | 已冻结 |
| 成本 | 档案约 35 秒、0.18 美元/题（CC 自报）；Sonnet 直接预测中位 20 秒；Haiku 判断远低于此 | 实测 |
| 多 Agent 执行标签 | **公开榜 14 家 × 261 道（含每题真实花费）**；rebench 100：DS 进行中，Sonnet/Haiku/GLM/Kimi 通道已验证 | 前者现成；后者待跑 |
| 评测脚本 | AUC/配对重抽样（各 analyze*.py）；缺 Brier/LogLoss/ECE 统一脚本 | 新增一个统一评测脚本 |

## 3. 预测方法对比（主线 B，P1）
同一题集、同一信息条件：
1. 统计：Agent 整体通过率（常数）、仓库历史、相似题、只看题面特征。
2. **强基线：题目难度预测 + Agent 整体能力**（逻辑模型 p = σ(能力_a − 难度_x)，难度用事前可得的通用预测，能力用训练折估计）。Foresight 必须在它之上有增量，否则如实报告。
3. 直接判断：Sonnet / Opus / Haiku / DS / GLM 读仓库直接给概率。
4. 工作流：档案 + Haiku 判；档案 + Sonnet 判；档案 + 案例；规则；经验卡。
5. Agent-specific：在 4 的输入上加目标 Agent 档案（整体通过率、成本、行为习惯）。
6. 成本档：便宜查证 + 强判断 / 强查证 + 便宜判断 / 一步直接判断。
指标：AUROC、Brier、LogLoss、ECE + 可靠性图、每题成本（token、美元、秒）、按仓库分组的重抽样区间与配对比较。

## 4. Routing 实验设计（P2/P3）
### 4.1 测试床
- **A. 公开榜离线反事实（现在就能做）**：SWE-bench Multilingual 261 道 × 14 家，结果与每题真实花费都公开。候选池两组：
  - 成本差异池：gpt-5-mini（0.05 美元，39%）/ minimax-2.5（0.10 美元，69%）/ Claude 4.5 Opus（0.83 美元，70%）。理想派活 79%，最强单一 70%，44% 的题三家结果不一致。
  - 能力相近池：DeepSeek 3.2 / GLM-5 / Claude 4.5 Sonnet。理想 80%，最强 70%，31% 不一致。
  - 局限：公开题较早，存在记忆污染风险；执行框架是 mini-swe-agent，与我们的不同。只作「离线策略评估」。
- **B. 我们自己的 rebench 100 道（主证据）**：DS + GLM（+ Sonnet、Haiku、Kimi），同一 harbor 环境、同轮数和时限。未跑完的题不计失败，不按任何模型成败选题。
### 4.2 方法
Random / Cheapest / Strongest（验证集最高通过率）/ Historical（整体通过率 + 任务特征）/ Difficulty-aware（第 3 节强基线）/ LLM Direct Router（统一上下文直接选 Agent）/ **Foresight-guided**（Agent-specific 概率 + 成本）/ Oracle（仅分析用上界）。
### 4.3 决策规则
质量优先（选 p 最高）、预算约束（预算内最大化 p）、效用（argmax p·V − c，V 取多组，做敏感性分析）。
### 4.4 指标与检验
成功率、每题平均成本、每个成功的成本、总成本（含预测器成本）、平均/P90 延迟、决策 regret、成本—成功率帕累托曲线；任务级重抽样区间，配对比较。
### 4.5 关键消融：预测质量如何转化为路由收益
固定候选池与规则，依次替换：只用整体能力 → 通用难度 → Agent-specific → 增强工作流 → Oracle。分解排序错误、校准错误、成本估计错误各自的损失；如果 AUROC 更高而决策收益不变，单独分析原因。
### 4.6 冻结与切分
所有策略和预测在揭晓前冻结；按仓库分 验证/测试；验证集调 V 和阈值，测试集只评一次；保留全部运行，不挑最好轨迹。

## 5. 成本、依赖与风险
| 项 | 调用 | 估计 |
|---|---|---|
| 测试床 A：Agent-specific 判断（3 候选 × 约 140 道有档案的题，Haiku） | 约 420 次短调用 | 很低 |
| 测试床 A：补档案（剩余约 120 道公开题，Sonnet 读仓库） | 约 120 次 | 约 22 美元额度 |
| 测试床 B：rebench 档案（100 道，Sonnet） | 100 次 | 约 18 美元额度 |
| 测试床 B：Agent-specific 判断（5 个执行者 × 100，Haiku） | 500 次 | 低 |
| 测试床 B：执行（DSH） | Sonnet 22 / Haiku 4 / GLM 5 / Kimi 待测 美元 | 已报 |
风险：可路由空间可能有限（多数题各家同成同败）；Agent-specific 增量可能不显著；rebench 上 DS 已跑完一部分，Agent-specific 预测必须在各执行者开跑前冻结。

## 6. 表与图规划
- 表 1 预测方法主表（AUROC/Brier/ECE/成本），前瞻 + rebench。
- 表 2 预测器 × 执行者矩阵（预测能力 vs 执行能力排序）。
- 图 1 可靠性图（直接判断 vs 工作流）。
- 图 2 成本—成功率帕累托（测试床 A、B 各一张）。
- 表 3 路由方法对比（成功率、成本、每成功成本、regret，带区间）。
- 图 3 消融：预测质量 → 路由收益阶梯。

## 7. 执行清单（按优先级）
- P0 DS 跑满 rebench 与预注册 77 道 → 揭晓三个预注册实验（DSH 跑，我分析）。
- P0 统一评测脚本（AUROC/Brier/LogLoss/ECE/分组区间）。
- P1 方法 v4 扩样本结果（进行中，今晚）。
- P1 在 rebench 未被其他执行者跑过之前，冻结档案 + Agent-specific 预测（需先确认额度）。
- P2 测试床 A 离线路由（零执行成本）。
- P2 测试床 B 离线路由（等 GLM/Sonnet 在 rebench 跑完）。
- P3 小规模端到端（20~30 道未见题，完整记录各阶段成本）。
- P4 Future Work：Foresight-aware Agent Manager、动态多轮路由、联合优化。
