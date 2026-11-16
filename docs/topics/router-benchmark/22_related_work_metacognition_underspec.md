# 相关工作核查：元认知 / 自我预测 / 需求不完整（2026-11-15 20:4x）

核实状态：「已核」= 我用检索确认了论文存在与摘要要点；「DSH 提供、未核」= 未由我独立确认。

## A. 模型能否预测自己能不能做成（元认知）
- 已核：Barkan, Black, Sourbut. *Do Large Language Models Know What They Are Capable Of?* arXiv 2512.24661（2025-12）。BigCodeBench 单步 + SWE-bench Verified 多步；所有模型**过度自信**，多数判别力好于随机；更新更大的模型判别力不一定更强（Claude 系列例外）；多步任务中越做越过度自信；给失败经验后部分模型改善。
  - 与我们的关系：我们发现 DS 预测自己是**系统性悲观**（平均以为 43% 会挂，实际约 10%）且判别接近随机——方向与其相反，值得报告；我们是仓库级、先预测后运行、多模型交叉。
- 已核：Hathidara. *Can an Agent Learn to Predict Its Own Failure? Outcome-Grounded Confidence Calibration in LLM Agents.* arXiv 2610.18614（2026-10）。GRPO 用整条轨迹的成败校准每步信心，AUROC 从近随机提到 0.68~0.85（ALFWorld/TextWorld/WebShop，Qwen2.5-7B）。说明「自我失败预测」可训练。
- DSH 提供、未核：MIRROR（arXiv 2604.19809）、Metacognitive Monitoring Battery（2604.15702）、综述 2607.11881、Beyond Confidence（2605.07806）、Agentic Metacognition（2509.19783）、Decoupling Metacognition from Cognition（AAAI 2025）。

结论：「元认知基准」「自我预测」都已有人做，单独以此为主贡献不新。

## B. 需求不完整（underspecification）与编程智能体
- 已核（检索摘要级）：
  - Ambig-SWE（ICLR 2026，arXiv 2502.13069）：构造欠指定版 SWE-bench Verified，智能体可向持有完整需求的模拟用户提问。
  - Ask or Assume?（arXiv 2603.26233）：何时提问；欠指定版 69.4% vs 完整题面 70.8%。
  - Dialogue-SWEBench（arXiv 2606.13995）：智能体只在 1~2% 的交互里提问；引用的分析称 SWE-bench 76% 的 issue 至少部分欠指定。
  - Asking What Matters（arXiv 2604.14624）：训练提更好的澄清问题。
  - SWE-RPG（arXiv 2608.09072）：分阶段评需求澄清/规划/编码。
- 与我们的差别：它们大多**人为删减题面**、再让智能体**问模拟用户**；我们研究的是**原始题面本身就缺**、而缺的部分**写在仓库里**（既有约定、并列实现、老测试），没有用户可问——需要从仓库自己推断；并且我们在**动手前**预测这种落差会不会导致失败，再用**仓库推断出的落差清单**做干预。

## C. 对论文定位的影响
- 不主打「元认知基准」或「欠指定提问」，两者都已拥挤。
- 可主打的组合：真实仓库级任务上的「**仓库内隐需求落差**」——(1) 现象与归因；(2) 先预测后运行的测量协议与跨模型矩阵（含「查到 vs 判准」拆分）；(3) 仓库推断落差清单的干预效果。必须与 A、B 中的工作逐条对比。

## 补充（2026-11-16）：最接近的工作与派活证据
- **Agent Psychometrics**（arXiv 2604.00594，2026-04；v2 2026-07）：预测 LLM×脚手架在编程任务上的逐题成败。新题无需他家在该题的结果；特征 = 题面、仓库上下文（审计 Agent 探索）、**标准答案与测试**，LLM（Opus 4.6）按评分细则打分 + 嵌入 → 岭回归。留出题 AUC：SWE-bench Verified 0.84、Pro 0.76、GSO 0.79、Terminal-Bench 2.0 0.79；oracle 0.92–0.95。自述：Agent 为类别变量，无法推广到全新 LLM/脚手架；加入「越特权的信息越有帮助」。
  区别：(1) 我们不使用标准答案/测试（真实派活时不可得）；(2) 我们测的是 LLM 自身的判断力并做跨模型比较、归因与干预，对方构建单一预测器；(3) 我们的判断对未见过的做题模型零样本可用。待做：把其方法作为基线；加「给判断者看标准答案」的信息上限对照。
- **DecisionBench**（arXiv 2605.19099，2026-05）：编排模型向 11 个他家模型派活（GAIA、τ-bench、BFCL），派对率（fidelity@1）7.5%–29.5%，完美派活的反事实上限比实测高 15–31 分。可作「Agent 不会估别人、损失大」的动机证据。
- 相邻：PredictaBoard（2502.14445）、100 instances（2409.03563）——评估器预测逐题成败，分布外较弱；EarlyEval（2609.02783）——运行中途预测；Predict-before-execute ML agents（2601.05930）——不运行比较两个方案。
