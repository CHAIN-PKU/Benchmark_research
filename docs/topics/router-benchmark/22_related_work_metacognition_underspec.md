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
