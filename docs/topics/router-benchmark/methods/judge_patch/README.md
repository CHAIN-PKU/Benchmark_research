# 判卷实验：只看题面和补丁、不运行，判断补丁能否通过隐藏测试（2026-11-15）

- 题：220 道（tasks.json），补丁为 DS 实际提交的补丁；标签 labels.csv（1 = 通过，基率约 0.8）。
- 输入：题面 + 候选补丁；不给标准答案、不给隐藏测试、不运行。脚本 judge_patch.py。
- 判断者：Claude 侧 Haiku / Sonnet / Opus（out/ 下各一目录，.err 为解析失败记录）；DS、GLM 由 DSH 在服务器上跑（最终表：服务器 benchmark_router_paper/judge_auc_final_20261116.csv）。
- AUC（p_pass 对「通过」，同一批 220 道；DS 196 道有效）：Opus 0.81、Sonnet 0.74、Haiku 0.60、GLM 0.54、DS 0.51。
- 读法：判卷与事前预测的模型排序一致，是同一种判断力在两个场景的表现；与「会写代码」不同（DS 做题约 75–80% 通过，判卷接近瞎猜）。
- 未入库：题面原文（issue/）与补丁原文（patches/，1.3MB）留在本机暂存，可由 tasks.json 从数据集重建。
