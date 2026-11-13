# 08 相关工作调研：运行前预测（pre-run prediction）某个模型能否解出某道软件工程题

调研日期：2026-11-13。方法：网络检索 + 逐篇打开 arXiv/会议页面核对标题、作者、年份、编号。
标记约定：【事前】= 预测时不需要在该题上运行任何模型；【事后】= 需要先让某模型（便宜模型或目标模型）在该题上跑过（哪怕只跑一部分）；「未核」= 本次没能在原文中核实。
说明：下表数字大多来自摘要或页面摘录，除特别注明外未逐页核对原文表格。

## 0. 一句话结论

- 最贴近我们设定的工作只有两篇：Ge 等的 Agent Psychometrics（智能体心理测量学，arXiv 2604.00594）和 Al-Haque & Johnson 的 ESEM 2026 论文。前者用「题面+仓库+补丁+测试」特征预测单题成功率，后者用静态特征（补丁碎片度、仓库规模）预测难度。
- 这两篇都用了「金标准补丁/测试补丁」作特征（我们预测时是拿不到的，真实场景里题目解出来之前没有答案），也都靠多个智能体的大量历史作答数据拟合，不是「单模型、~100 题」设定。
- 路由器（router）类工作（RouteLLM、RouterDC 等）预测的是「哪个模型更好」，输入多为纯文本问题，规模是几千到几十万条，单模型 ~100 题下几乎无法照搬，但其核心部件（文本嵌入 + 简单分类器）可作为廉价基线。
- 「模型能否自知」（P(IK)、智能体过度自信）是另一条线：让模型自己预测，成本低但校准差。

## 1. 路由器（LLM Router）类

| 论文 | 引用与链接 | 预测时输入 | 事前/事后 | 方法与指标 | 数据规模 | 代码 | 在我们设定下复现难度 |
|---|---|---|---|---|---|---|---|
| RouteLLM | Ong 等, "RouteLLM: Learning to Route LLMs with Preference Data", ICLR 2025, arXiv:2406.18665 (https://arxiv.org/abs/2406.18665) | 仅问题文本 | 事前 | 二分类路由器（强弱两模型二选一），用 Chatbot Arena 人类偏好数据训练，含相似度加权、矩阵分解、BERT 分类器、因果 LLM 四类；报告在部分基准上成本节省 2 倍以上且质量基本不降 | 数万条偏好对（具体「未核」） | 公开 | 中。目标是「强/弱谁赢」，不是「单模型对错」；需改成二分类标签。其「矩阵分解/BERT」思路可降维用在 100 题上但样本太少 |
| RouterBench | Hu 等, "RouterBench: A Benchmark for Multi-LLM Routing System", arXiv:2403.12031 (https://arxiv.org/abs/2403.12031)，期刊/会议「未核」（页面未标注） | 问题文本 | 评测框架 | 提供 405k+ 条多模型推理结果与路由理论框架，比较 KNN/MLP 等路由器 | 405k 推理结果 | 公开 | 低（只是数据集与框架，无软件工程题） |
| Hybrid LLM | Ding 等, "Hybrid LLM: Cost-Efficient and Quality-Aware Query Routing", ICLR 2024, arXiv:2404.14618 (https://arxiv.org/abs/2404.14618) | 仅问题文本 | 事前 | 训练路由器预测「小模型回答质量不低于大模型」的概率（用 BARTScore 作合成标签），测试时可调阈值；最多少调用大模型 40% 且质量不降 | 「未核」 | 「未核」 | 低-中。「预测小模型是否够用」与我们的「单模型是否解出」最接近，可直接改为二分类 |
| RouterDC | Chen 等, "RouterDC: Query-Based Router by Dual Contrastive Learning for Assembling Large Language Models", NeurIPS 2024, arXiv:2409.19886 (https://arxiv.org/abs/2409.19886) | 仅问题文本 | 事前 | 编码器 + 每个 LLM 的可学习嵌入，双重对比学习；域内 +2.76%、域外 +1.90%（相对最佳单模型） | 「未核」 | 公开（摘要称有 GitHub） | 中。需要多模型的作答数据；单模型下退化为文本编码器分类 |
| GraphRouter | Feng, Shen, You, "GraphRouter: A Graph-based Router for LLM Selections", ICLR 2025（页面仅标 arXiv，会议「未核」）, arXiv:2410.03834 (https://arxiv.org/abs/2410.03834) | 任务/问题/LLM 三类节点的异构图 | 事前 | 边预测估计「某 LLM 回答某问题的效果与成本」；比既有路由器至少高 12.3% | 「未核」 | 「未核」 | 高（依赖多模型、多任务图，我们不适用） |
| EmbedLLM | Zhuang 等, "EmbedLLM: Learning Compact Representations of Large Language Models", arXiv:2410.02223 (https://arxiv.org/abs/2410.02223)，会议「未核」 | 问题嵌入 + 模型嵌入 | 事前（模型嵌入需历史作答） | 编码-解码，预测「模型 × 题」正确性矩阵 | 「未核」 | 公开（摘要称发布数据、代码） | 中。本质是矩阵分解，需要许多模型的作答矩阵 |
| IRT-Router | Song 等, "IRT-Router: Effective and Interpretable Multi-LLM Routing via Item Response Theory", ACL 2025（pp.15629-15644）, arXiv:2506.01048 (https://arxiv.org/abs/2506.01048) | 查询文本；新查询用「语义相似的历史题」热启动（warm-up） | 事前（需历史题的多模型作答） | 项目反应理论（IRT，用「能力 - 难度」解释作答对错的统计模型）建模；20 个 LLM、12 个数据集；输出可解释的能力与题目难度 | 20 LLM × 12 数据集 | https://github.com/Mercidaiha/IRT-Router | 中。IRT 部分在单模型下无法估能力；其「相似题 kNN 热启动」可降级复现 |
| Zooter | Lu 等, "Routing to the Expert: Efficient Reward-guided Ensemble of Large Language Models", arXiv:2311.08692（会议「未核」） | 问题文本 | 事前 | 用奖励模型打分蒸馏出路由函数；在 26 个子集上整体优于最佳单模型，44% 任务排第一 | 26 子集 | 「未核」 | 低价值（目标是选模型，不是预测成败） |
| MixLLM | arXiv:2502.18482（作者与会议均「未核」，仅二手来源） | 问题文本 | 事前 | 基于上下文老虎机（contextual bandit，边用边学的选择算法）的动态路由，平衡质量/成本/延迟 | 扩展 RouterBench | 「未核」 | 低价值 |
| FrugalGPT | Chen, Zaharia, Zou, "FrugalGPT: How to Use LLMs While Reducing Cost and Improving Performance", arXiv:2305.05176（2023；正式发表于 TMLR，「未核」） | 先让便宜模型作答，再用一个打分器判断是否可信 | **事后（需要先运行模型）** | LLM 级联（cascade）；最多降成本 98% 且持平 GPT-4，或同成本提 4% 准确率 | 「未核」 | 「未核」 | 不适用为「事前」基线，但可作为「事后」上界参考 |
| LLMRouterBench / RouterArena | LLMRouterBench: arXiv:2601.07206；RouterArena: arXiv:2510.00202（均仅见标题与二手摘要，作者与细节「未核」） | 文本 | 事前 | 统一评测多种路由器；有二手说法称多数方法在「性能优先」设定下表现接近（「未核」） | 大规模 | 「未核」 | 可用作现成的路由器实现集合 |

小结：路由器类文献的共同点是「输入=问题文本（+历史作答），标签=模型是否答对」，在通用问答上做；几乎没有针对「带仓库的软件工程题」的版本。

## 2. 软件工程 / 编码智能体：难度与成败预测

| 论文 | 引用与链接 | 预测时输入 | 事前/事后 | 方法与指标 | 数据规模 | 代码 | 复现难度（我们设定） |
|---|---|---|---|---|---|---|---|
| **Agent Psychometrics**（最相关） | Ge, Kryvosheieva, Fried, Girit, Hariharan, "Agent Psychometrics: Task-Level Performance Prediction in Agentic Coding Benchmarks", ICLR 2026 Workshop on Agents in the Wild, arXiv:2604.00594 (https://arxiv.org/abs/2604.00594) | 题面（issue）、仓库状态（由 GPT-5.4 审计智能体生成特征）、金标准补丁、测试；嵌入用 DeepSeek-R1-Distill-Qwen-32B | 对「新题」：事前（不跑新题），但要先有「别的题上多个智能体的作答」来拟合难度；用到金标准补丁/测试 → 在我们场景属于「事前但信息更多」 | IRT 扩展：先拟合每题难度，再用特征做岭回归预测难度；把智能体能力拆成 LLM + 脚手架。新题 AUC（留出题）：SWE-bench Verified，基线 0.718 / 嵌入 0.824 / LLM 评审特征 0.840 / 组合 0.841 / 上界 0.945；SWE-bench Pro 0.656/0.752/0.743/0.763/0.918；GSO 与 Terminal-Bench 2.0 也有。新基准迁移时 SWE-bench Pro 仅 0.696（LLM 评审） | SWE-bench Verified 约 500 题等，各基准智能体数「未核」 | https://github.com/dariakryvosheieva/agent-psychometrics（页面由正文给出，未单独打开仓库） | 中。「嵌入→岭回归」和「LLM 评审打分→回归」两个臂可直接复现；但其 IRT 难度需要多个智能体的作答，单模型下用「该模型的 0/1 标签」直接做回归即可；注意其基线 0.718 就是「按平均成功率预测」 |
| What Makes Software Issue Resolution Tasks Difficult for Agents? | Al-Haque & Johnson (George Mason Univ.), ESEM 2026, LIPIcs vol.394 (https://drops.dagstuhl.de/entities/document/10.4230/LIPIcs.ESEM.2026.3) | 补丁特征（碎片度）、仓库规模、提示语言学特征 | 事前（但补丁特征来自金标准补丁） | 集成模型 + SHAP；AUC = 0.863；难度主要由补丁碎片度和仓库规模驱动 | CoderForge-Preview 轨迹，题数「未核」 | https://github.com/ebtesam25/diffmodel-esem | 低-中。特征易算，但需金标准补丁。仅靠仓库规模/语言可构成「仓库先验」基线。注意二手评述提醒：同一数据上「所有题给同一分数」的 AUC 也有 0.715（需谨慎解读，来源为博客，未核） |
| Reliable and Efficient Amortized Model-based Evaluation | Truong, Tu, Liang, Li, Koyejo, ICML 2025 (PMLR 267), arXiv:2503.13335 (https://arxiv.org/abs/2503.13335) | 题目文本 → 嵌入 → 线性模型预测 IRT 难度 | 事前（需先有多模型作答拟合 IRT） | 摊销校准（amortized calibration，用文本直接预测难度，不用重新拟合）；评测查询量平均省约 50%（ICML 版；arXiv v1 为 53%） | 183 个 LM（ICML 版） | https://github.com/sangttruong/reeval | 中。「文本嵌入→难度」直接对应我们的「嵌入 + 逻辑回归」基线 |
| Triage | Madeyski, "Triage: Routing Software Engineering Tasks to Cost-Effective LLM Tiers via Code Quality Signals", arXiv:2604.07494 | 代码健康度指标（CodeHealth，可维护性分数） | 事前 | 在 SWE-bench Lite 300 题上比较启发式阈值/训练分类器/事后最优；仅 5 页，具体 AUC「未核」 | 300 题 | 未提供 | 低。代码质量特征可作为特征基线之一 |
| SWE-Router | Son 等, "SWE-Router: Routing in Multi-turn Agentic Software Engineering Tasks", ICML 2026 Deep Learning for Code Workshop, arXiv:2607.00053 | 题面 + 便宜模型的部分轨迹 | **事后**（便宜模型先探索几轮） | 价值头（value head）预测便宜模型最终能否解出；声称只看题面的嵌入基线显著更差（二手摘要，数字「未核」） | 「未核」，并发布多 LLM 轨迹数据集 | 「未核」 | 中。与我们「不运行」的约束不同，可当作「运行后」上界 |
| Scrouting (SuperScout) | Bhola, Krishnan, NS, "Scrouting: Cost-Aware Routing of Coding Agents by Scouting the Repository First", arXiv:2608.04804 | 7B 侦察模型先探索仓库的隐藏状态 + 题面 | **事后**（运行侦察模型） | SWE-bench Pro Python 子集 266 题，解出 159 vs 最佳单模型 158，成本约 1/5；作者自称增益主要来自「交接文档」而非路由 | 266 题 | 未提供 | 高，不属事前 |
| TwinRouterBench | arXiv:2605.18859（作者「未核」） | 步骤级路由；二手摘要称单模板 LLM 路由器（Claude Opus 4.6）在 147 个「高难度」步骤中只预测出 7 个，而在静态标签上训练的逻辑回归路由器性价比最好 | 步骤级，事后 | 「未核」 | 「未核」 | 「未核」 | 仅作旁证：零样本 LLM 判断偏保守，简单逻辑回归反而强 |
| SWE-bench Verified 难度标注 | OpenAI, "Introducing SWE-bench Verified"，2024（https://openai.com/index/introducing-swe-bench-verified/），人工估计解决时长分档（<15 分钟、15 分钟-1 小时等），三位标注者取最严重标签 | 人工标注（人读题与补丁） | 事前，但成本为人工 | 标注与智能体成败相关，具体相关系数「未核」；Epoch AI 统计 <15 分钟题平均改 5 行 | 500 题 | 标注公开 | 对我们的数据集无现成标注，可让人/LLM 仿标 |

## 3. 项目反应理论（IRT）与高效评测

| 论文 | 引用与链接 | 输入 | 事前/事后 | 方法与数字 | 代码 | 备注 |
|---|---|---|---|---|---|---|
| tinyBenchmarks | Polo 等, "tinyBenchmarks: evaluating LLMs with fewer examples", ICML 2024（会议「未核」，页面仅标 arXiv）, arXiv:2402.14992 (https://arxiv.org/abs/2402.14992) | 少量题目的作答 | 事后（需要目标模型在锚点题上作答） | IRT++：100 题估计 MMLU 准确率，平均误差约 2% | 公开 felipemaiapolo/tinyBenchmarks | 估的是「整体分数」，不是单题成败；「冷启动」题难度不直接支持 |
| metabench | Kipnis 等, "metabench: A Sparse Benchmark of Reasoning and Knowledge in LLMs", ICLR 2025, arXiv:2407.12844 (https://arxiv.org/abs/2407.12844) | 稀疏题子集的作答 | 事后 | 5000+ 模型、28,632 题，缩到 <3%；单基准 RMSE 1.24%；单一公共因子与总分 Spearman 0.94 | 「未核」 | 同上，估总分 |
| 文本预测 IRT 难度（教育测量） | Scarlatos 等 arXiv:2507.05129（模拟学生作答再拟合 IRT，明确指出不能用于全新题目）；Jain 等 arXiv:2502.17785（LLM 零样本分类阅读理解题难度）；arXiv:2602.06631（10 个 LLM 预测 1,031 道 ENEM 题的 IRT 难度，指出低误差可掩盖排序差）；Hoyl arXiv:2602.00034（LLM 提取特征 + 嵌入预测 IRT 难度，二手摘要称相关 0.77，设定「未核」） | 题目文本 | 事前 | 均为教育考试题，标签是人类考生难度，不是 LLM 成败 | 「未核」 | 可借鉴「LLM 零样本评难度」「相关性/排序指标而非仅误差」的做法 |

## 4. 模型自知（自己预测自己能否成功）

| 论文 | 引用 | 输入 | 事前/事后 | 方法与数字 | 复现难度 |
|---|---|---|---|---|---|
| Language Models (Mostly) Know What They Know | Kadavath 等 (Anthropic), arXiv:2207.05221 (https://arxiv.org/abs/2207.05221)，2022，会议「未核」 | 问题（P(IK)：模型自评「我是否知道答案」）；或问题 + 答案（P(True)） | P(IK) 事前；P(True) 事后 | 在模型上加价值头训练预测 P(IK)；大模型在域内表现好，跨任务校准较差 | 需要可微调的模型，我们若用 DeepSeek API 则只能做提示版（零样本自评） |
| Agentic Uncertainty Reveals Agentic Overconfidence | Kaddour 等, arXiv:2602.06948 (https://arxiv.org/abs/2602.06948)，2026 | 让智能体在执行前/中/后自报成功概率 | 事前版有（执行前自评） | 普遍过度自信（例：实际成功率 22% 的智能体预测 77%）；执行前评估信息更少，却往往比执行后复盘更能区分成败（差异不总显著）；用「找 bug」式对抗提示校准最好 | 低，直接可作「LLM 自评」基线，零成本 |

## 5. 推荐复现的基线（从易到难，共 6 个）

1. 仓库/语言先验（B0，最低线）：只用仓库名、语言、仓库规模（文件数、行数）、题面长度，做逻辑回归或「按仓库平均成功率」预测。参考：Al-Haque & Johnson 的「仓库规模」结论；Agent Psychometrics 的「平均成功率」基线（AUC 0.656-0.732）。难度：很低，半天。必须报：「全部预测同一个分数」的 AUC 作为零点，避免被 0.5 附近的虚高迷惑。
2. 文本嵌入 + 逻辑回归（B1）：题面（可加仓库 README）过编码器，交叉验证训练。参考：Truong 等 2025 的线性难度预测器；RouteLLM 的 BERT 分类器；Agent Psychometrics 的「嵌入臂」（Verified 上 0.824，但那是用多智能体拟合难度后的结果，单模型 ~100 题会明显更低，需自行评估）。难度：低。
3. LLM 零样本评审（B2）：让强模型读题面+仓库摘要，直接给出「该模型能否解出」的概率，或按 Agent Psychometrics 的 15 个评审特征打分后再做回归。参考：Agent Psychometrics 的「LLM-judge 臂」（Verified 0.840）；Kaddour 等的执行前自评。难度：低-中，有 API 成本。
4. 模型自评（B3）：让目标模型（DeepSeek）自己在执行前给成功概率。参考：Kaddour 等；Kadavath 等 P(IK) 的提示版。难度：低。预期校准差，但可检验「自知」是否成立。
5. 代码健康度/补丁结构特征（B4）：用 Triage 的 CodeHealth、Al-Haque & Johnson 的仓库/补丁特征。注意补丁特征依赖金标准，只能作「信息更多」的参照上界，不能算严格事前。难度：中。
6. 最强已发表：Agent Psychometrics 组合臂（B5，「嵌入 + LLM 评审 + 仓库状态特征」→ 岭回归），按其开源代码适配为单模型二分类；并附带「事后」参照（SWE-Router 式便宜模型试探 / FrugalGPT 级联）作为非事前上界。难度：中-高。

评估建议：~100 题下，用重复分层交叉验证，报告 AUC 及其置信区间（自助法）、Brier 分数（概率误差）和校准曲线；与「全预测同一分数」基线比；所有嵌入/特征挖掘都必须在训练折内完成，避免泄漏。

## 6. 我们的方法填补的空白

- 文献中的预测器几乎都是「多智能体 × 多题」的大矩阵拟合（IRT、路由器），预测的是「某题对一类智能体的难度」，需要数十个模型的作答；我们的设定是单个具体模型（如 DeepSeek）、~100 题，标签稀少。
- 已有静态特征研究（Al-Haque & Johnson、Agent Psychometrics）依赖金标准补丁/测试，真实预测时拿不到；我们只用题面 + 仓库，是严格意义上的事前。
- 已有「LLM 评审」特征是通用、人工预设的（Agent Psychometrics 的 28 个特征）；我们做的是针对特定模型、从仓库与题面中「挖掘」其失败相关特征，再交给强而慢的决策模型综合判断（慢思考、不在乎延迟），相当于把「特征挖掘 + 判决」分开。
- 路由器类文献追求低延迟（毫秒级的小分类器）；我们没有延迟约束，因此允许用强模型做慢速判决，这是一个文献中少见的设定（TwinRouterBench 的二手摘要还提示零样本 LLM 判断可能偏保守，需要校准，这本身是可研究点）。
- 需要在论文中诚实说明：以上空白属于「设定差异」；是否真的更好，要靠与第 5 节基线的对比实验证明。

## 7. 论文出处（会议/期刊）汇总

- ICLR：Hybrid LLM（2024）、RouteLLM（2025）、metabench（2025）；GraphRouter、EmbedLLM 也被二手来源称为 ICLR 2025（「未核」）
- NeurIPS：RouterDC（2024）
- ICML：Truong 等的摊销评测（2025）；tinyBenchmarks（2024，「未核」）；RouterBench（二手来源称 ICML 2024 workshop，「未核」）
- ACL：IRT-Router（2025）
- ESEM：Al-Haque & Johnson（2026）
- Workshop：Agent Psychometrics（ICLR 2026 Agents in the Wild）、SWE-Router（ICML 2026 Deep Learning for Code）
- 仅 arXiv（未核实是否已正式发表）：Zooter、MixLLM、FrugalGPT（后者另有 TMLR 说法「未核」）、Triage、Scrouting、TwinRouterBench、Kaddour 等的智能体过度自信、Kadavath 等
- 注：2026 年的 arXiv 编号（2604、2605、2607、2608 开头）来自检索页面，已打开摘要页核对其中 2604.00594、2604.07494、2607.00053、2608.04804、2602.06948；TwinRouterBench（2605.18859）、LLMRouterBench、RouterArena、MixLLM 仅见检索结果列表，未打开。

## 8. 未核事项清单

RouterBench 与 GraphRouter/EmbedLLM 的正式发表信息；Hybrid LLM、RouterDC 的数据规模与代码链接；Agent Psychometrics 各基准的题数与智能体数（正文后 71k 字符未读）；SWE-Router 的数值结果与代码；TwinRouterBench 与 LLMRouterBench 的作者与结论；ESEM 论文的题数；二手博客（agentpatterns.ai、codex.danielvaughan.com）中的数字只作线索，不作引用依据。

---

## 第二轮补充（assessor / benchmark 路由 / 编程智能体）

调研日期：2026-11-13。方法同第一轮：检索 + 打开 arXiv 摘要页核对。本节不重复第一轮已列论文，只在需要时交叉引用（如 Agent Psychometrics、Al-Haque & Johnson、SWE-Router、Scrouting、Triage）。下文「未核」= 没在原文核实；摘要页没给的数字一律不写。
先说结论：PI 的直觉是对的，「事前预测某个具体模型能否答对某个具体实例」有一整条成熟的研究线，就是 Cambridge / Valencia 的 assessor（评估器，一个外部小模型，专门预测另一个 AI 系统在某题上是否会出错）线。但这条线几乎全在通用问答/推理题上做，没有碰过「带仓库的软件工程智能体题」；编程路由线（SWE-Router、Scrouting 等）则多数需要先跑一点。

### A. Assessor / 可预测 AI 线（Hernández-Orallo、Zhou 等）

| 论文 | 核实情况 | 要点 |
|---|---|---|
| **ADeLe / 通用量表**（最接近） Zhou, Pacchiardi, Martínez-Plumed 等 26 人，"General Scales Unlock AI Evaluation with Explanatory and Predictive Power" | arXiv:2503.06378（https://arxiv.org/abs/2503.06378，已打开）；后发表于 Nature 652, 58-67 (2026)，DOI 10.1038/s41586-026-10303-2（来自检索结果，未打开 Nature 页面，「未核」） | 用 18 条评分细则（rubric，给题目打「认知需求等级」的评分标准，0-5+ 分）让 GPT-4o 给每道题打需求分；再对每个被测模型用随机森林（random forest，一种决策树集成）从「需求分」预测它在新题上对不对。数据：16,108 题、63 个任务、20 个基准、15 个 LLM。arXiv v1 的 AUROC（区分度，0.5=瞎猜，1=完美）加权平均：同分布 0.839（GloVe 词向量 0.805，微调 LLaMA 0.840）；新任务 0.810（0.740 / 0.788）；新基准 0.747（0.480 / 0.692）。校准误差 ECE（预测概率与实际频率的偏差，越小越好）：0.011 / 0.022 / 0.037，均优于基线。题目标注只需题面，是「事前」；但每个被测模型必须先在 ADeLe 题库上跑过，得到成败标签来训练该模型自己的预测器。覆盖是文本模态；是否含代码题「未核」。代码与数据：称开源，仓库链接未在页面核到，只给了 https://kinds-of-intelligence-cfi.github.io/ADELE |
| **Reject Before You Run** Zhou, Martínez-Plumed, Hernández-Orallo, Ferri, Schellaert, "Reject Before You Run: Small Assessors Anticipate Big Language Models" | CEUR-WS Vol-3169 paper 4（https://ceur-ws.org/Vol-3169/paper4.pdf），EBeM@IJCAI 2022（来自检索摘录；PDF 无法解析，故数字「未核」） | 最早的「单模型 + 实例级 + 事前」做法：用小模型当 assessor，预测大模型在 BIG-bench 的数据整理任务上哪些实例会失败，从而拒答/跳过。AUROC 等数字「未核」 |
| **Predictable AI** Zhou 等（Hernández-Orallo 末位作者）| arXiv:2310.06167（https://arxiv.org/abs/2310.06167，v3 2025-01；检索页确认，未逐页读）| 立场/框架论文：形式化「可预测性」，讨论预测器种类、有效性与可预测性的权衡，主张可预测性应优先于性能。无实验数字 |
| **PredictaBoard** Pacchiardi 等 7 人 | arXiv:2502.14445，ACL Findings 2025（https://arxiv.org/abs/2502.14445，已打开）| 评估「LLM + assessor」组合的基准：用「准确率-拒答曲线」（拒掉预测会错的题后，剩下题的准确率）打分；assessor 不得用 LLM 的输出，但可用其内部激活。作者说可扩展到 LLM 智能体，但未做。代码：https://github.com/Kinds-of-Intelligence-CFI/PredictaBoard |
| **100 instances is all you need** Pacchiardi, Cheke, Hernández-Orallo | arXiv:2409.03563，KDD 2024 评测研讨会（已打开）| 新模型只需在约 100 道参考题上跑一遍，再配合题目特征训练通用 assessor，就能预测它在未见题上的成败；同分布下与「该模型专属 assessor」相当，随机选参考题不比花哨选法差；分布外明显变差、「没有明显赢家」。摘要页无具体数字。与我们的「单模型 ~100 题」设定量级相同，是最直接的方法与预期参考 |
| **What should an AI assessor optimise for?** Romero-Alvarado, Martínez-Plumed, Hernández-Orallo | arXiv:2502.00365（已打开）| 在 20 个表格问题上研究 assessor 该用什么损失训练；结论：直接用目标指标训练不一定最好，logistic 损失等单调变换有时更好。可当训练细节参考 |
| **Scales++** Bean, Seedat, Chen, Schwarz | arXiv:2510.26384（已打开）| 用「认知需求嵌入」选小评测子集，免冷启动（不需要旧模型的作答记录）；预测的是整体分数（0.25% 子集误差 3.2%），不是单题成败；与 ADeLe 同思路的外部延伸 |

交叉观察：ADeLe 的「用需求分代替嵌入」在新基准上比嵌入基线（AUROC 0.48）强得多，说明「可解释的人工设计特征」比黑箱文本嵌入更能迁移，这与我们「挖掘特征再判决」的方向一致，但它的特征是通用的，不针对某个模型挖掘。

### B. Benchmark 驱动的路由与模型选择

| 论文 | 核实情况 | 要点 |
|---|---|---|
| **RouterEval** Huang 等（中山大学）| arXiv:2503.10657（已打开摘要检索），后见于 EMNLP 2025 Findings（检索页标 2025.findings-emnlp.208，「未核」）| 12 个评测、超 2 亿条、8500+ 个 LLM 的作答记录；发现路由器足够好时可超过池中最佳单模型（"model-level scaling up"）。通用任务，无软件工程智能体 |
| **EmbedLLM** | 第一轮已列；补充：可从其模型嵌入读出「擅长编程」等特性 | 需要许多模型的作答矩阵 |
| **Collaborative filtering 评测**（把 LLM 当用户、题当物品）| arXiv:2504.08781（仅见检索列表，作者与数字「未核」）| 挑区分度最大的题，再由相似模型的成绩预测目标模型在其余题上的成绩 |
| **Routesplain** Štorek 等（Columbia / Oracle），COLM 2026 | arXiv:2511.09373（已打开）| 首个面向软件任务的路由器：先抽取人类可读的「概念」（任务、领域、推理复杂度），仅凭概念路由（concept bottleneck，概念瓶颈：中间层必须是人能读懂的概念）。16 个 LLM、8 个软件任务（代码生成/修复、输入输出预测、CS 问答），不是仓库级智能体题。优于单模型，与黑箱 MLP 持平。事前、多模型 |
| **Agent-as-a-Router / ACRouter** Zhou 等 11 人 | arXiv:2606.22902（已打开）；代码 https://github.com/LanceZPF/agent-as-a-router | 提出 CodeRouterBench：约 1 万题、8 个前沿 LLM 的已验证成绩；发现「瓶颈是信息不是推理」，给路由器加上「任务维度的历史性能统计」相对提升 15.3%。ACRouter 在部署中边验证边学（Memory 记忆模块），不是一次性事前预测。这是最贴近「benchmark 驱动路由」的编程线工作：历史 benchmark 统计作为路由输入 |
| **CoDyn** | NeurIPS 2025 页面（https://neurips.cc/virtual/2025/131708，只见页面摘要，「未核」arXiv 编号）| 5 个模型 × 5 个编程任务，微调小 LLM 当分类路由器；声称持平最强模型、平均省 43% 成本（来自会议页摘要，「未核」原文）。事前、多模型 |
| **AdaptiveLLM** Cheng 等，Internetware 2025 | arXiv:2506.10525（已打开）| 用推理模型的思维链长度估难度（k-means 分 3 档）+ CodeBERT + XGBoost 选模型；相对 ComplexityNet pass@1 +7.86%，资源 -88.9%。代码生成题，不是仓库级。需先让一个推理模型生成思维链（带少量运行成本，是否算事前「未核」）|
| **per-query 模型选择**（EMNLP 2025 Findings 2025.findings-emnlp.456）| 仅见检索列表，标题与结论「未核」 | 称聚合基准分数不适合挑选针对具体问题的模型，思路与我们一致，需打开核对 |

小结：目前没找到「只用某模型自己的历史 benchmark 结果 → 事前预测它在新的仓库级 SWE 题上成败 → 用于路由」的完整工作。SWE-Router、Scrouting 都要先跑；Routesplain/CoDyn 是多模型、非仓库级；ACRouter 最接近但靠在线反馈。

### C. 编程智能体：事前难度/成败预测（补充第一轮）

| 论文 | 核实情况 | 要点 |
|---|---|---|
| **Predicting Task Difficulty Without Rollouts** Krsteski & Meyer | arXiv:2608.05797（已打开摘要）| 在 17 个智能体基准（含编程）上做「无需跑智能体」的事前难度预测。三点结论：AUC 会掩盖差的难度估计（应同时报基准内的排序相关）；token 级熵是有用信号；预测值与实际值的残差可暴露环境缺陷（数据污染、题目不可解）。基准内排序可恢复，跨基准迁移仍是开放问题。无代码链接。（二手来源称「全预测同一难度」基线 AUC 约 0.715，未在原文核到，「未核」）|
| **EarlyEval** Shi 等（上海交大 / 新加坡管理大学）| arXiv:2609.02783（已打开 HF 页面）；代码 https://github.com/inphotoo/earlyeval | 中途预测：根据部分轨迹提前停掉必成/必败的运行；SWE-bench Verified 上 95% 准确率、少 26% 步数，16 个智能体的排名相关 0.991。属事后（要先跑）|
| **Al-Haque & Johnson**（第一轮已列）补充 | 检索页称：54 个静态特征，XGBoost AUC 0.863，4.5 万多题、1553 个仓库；题面特征几乎无增益（ΔAUC ≤0.0021），仅仓库特征 AUC 0.839 | 对我们的重要提示：仓库规模/结构本身就能带来很高 AUC，题面文本可能增益很小；这些数字来自检索摘要，「未核」原文 |
| **Agent Psychometrics**（第一轮已列）补充 | 二手来源数字与第一轮不一致（如 Verified 0.787→0.848；跨基准 0.677/0.719），「未核」 | 引用时以原文为准，不用二手数字 |
| 执行前自评 | 检索「预测是否解出」没有找到专门校准分析（可靠性图、Brier）的 SWE 工作 | 与第一轮 Kaddour 等相同，仍是空白 |

### D. 第二轮对「新颖性」的影响

1. 「事前 + 单模型 + 实例级」不是新点子：Reject Before You Run（2022）、100 instances（2024）、ADeLe（2025，Nature 2026）已经做过，只是任务是问答/推理题。
2. 「用题目的可解释特征预测某模型成败并优于嵌入」也已被 ADeLe 证明（尤其新基准上）。我们不能说首创此范式。
3. 尚未被占的位置：(a) 带仓库的软件工程智能体题；(b) 特征不是预设量表，而是从该模型自己的历史 benchmark 失败里挖出来；(c) 严格事前（不含金标准补丁）并报告校准与 ~100 题小样本表现；(d) 以路由成本节省作为最终评估。需用实验证明，不是文献已保证的。
4. 必须补做的基线：ADeLe 式（通用需求量表 + 随机森林）、Pacchiardi 的「100 题参考集」、Al-Haque 的仓库特征。
5. 评估须按 Krsteski & Meyer 的提醒：报告「全预测同一分数」的 AUC 零点，和基准内排序相关，不能只报 AUC。

### E. 第二轮新增论文出处汇总

- Nature：ADeLe（2026，来自检索结果，「未核」原页）
- ACL Findings 2025：PredictaBoard
- COLM 2026：Routesplain
- NeurIPS 2025：CoDyn（页面摘要，「未核」）
- Internetware 2025：AdaptiveLLM
- KDD 2024 评测研讨会：100 instances
- EBeM@IJCAI 2022：Reject Before You Run
- 仅 arXiv（未核发表情况）：Predictable AI（2310.06167）、What should an AI assessor optimise for（2502.00365）、Scales++（2510.26384）、Agent-as-a-Router（2606.22902）、Krsteski & Meyer（2608.05797）、EarlyEval（2609.02783）、2504.08781
- 本轮「未核」清单：ADeLe Nature 版数字（上表用 arXiv v1）与代码仓库；Reject Before You Run 的数字；Predictable AI 与 PredictaBoard 的具体结果；CoDyn 的 arXiv 编号与数字；ACRouter 的二手数字（49.98% 等）；EMNLP 2025 per-query 选择论文；2504.08781 的作者。
