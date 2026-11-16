# 预注册：rebench 100 道上「针对执行者」的事前预测（2026-11-16 17:2x 冻结）
- 方法 v4：Sonnet 读修复前快照写仓库档案（out_dossier_rb/，100 份）→ Sonnet 判断（完整题面 + 档案 + 执行者档案）。
- 六组：blind（不告诉是谁）、DS、GLM、SONNET、HAIKU、KIMI，各 100/100（out_rb_target/）。执行者档案只用开跑前可得信息（我们自己的 DS 记录；其余为公开榜前代模型通过率）。
- 校验码：rb_dossier.sha256、rb_target_outputs.sha256。有效性：rb_validity.txt（DS 只在冻结时未开跑的题上算；SONNET、HAIKU 各剔除一道通道验证题）。
- 用途：第 6 章新题预注册（档案法 vs 强基线），第 7 章 rebench 离线 Routing。
- 主分析计划：各执行者 AUROC/Brier/ECE；blind vs 针对执行者（是否有超出题目难度的增量）；与「题目难度 + 模型整体能力」强基线比较。揭晓前不看任何准度。
