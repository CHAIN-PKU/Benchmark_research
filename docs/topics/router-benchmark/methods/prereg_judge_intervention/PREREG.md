# 预注册：判断者干预实验（新题，运行前冻结）2026-11-16 00:2x

假设 H5：弱判断者的差距主要在「风险定分量」；给出具体的定分量规则能改善其排序准度，且这种改善不是「多了提示」本身带来的。

数据：前瞻 123 道中 DS 尚未开跑的 77 道（ns_judge.json，00:2x 核对）；证据统一取 Sonnet 通用提示组已冻结输出中的 evidence 字段（≤3 条）。规则文本在本次之前已写定（judge_rubric.py 于 11-15 23:0x 在旧题上用过），本批新题未参与规则设计。

四组（只判断、不读仓库、单轮）：
- A 无干预：judge_reason.py
- B 具体定分量规则：judge_rubric.py
- C 通用风险清单（不给分量）：judge_generic.py
- D 打乱/反向分量规则：judge_shuffled.py
判断者：Haiku 5.5、Sonnet 5.5（Mac）；DeepSeek v4.1 flash、GLM（DSH）。每组每题 1 次（若预算允许再加 1 次）。

主分析（标签揭晓后）：每个判断者 B−A 的 AUC 差，配对自助法 95% 区间与配对置换检验；C、D 作为对照（预期 C≈A，D≤A）。辅助：Brier、平衡准确率。宽松/严格两种失败口径都报。
判定：B−A 的区间不含 0 且 D 不优于 A → 支持 H5；否则不支持，如实报告。

## 追加 1（2026-11-16 00:5x，Claude 侧冻结）
- Haiku、Sonnet × A/B/C/D 八组各 77/77 完成；全部输出的 sha256 见 `frozen_claude_side.sha256`（冻结时尚未看任何 DS 标签）。
- 逐题核对 DS 首次开跑时间（`ds_start_77.txt`，服务器 runs/ 目录最早条目时间）：冻结时 72 道未开跑，5 道（fmtlib__fmt-1683、fmtlib__fmt-2310、gin-gonic__gin-3820、gohugoio__hugo-12343、hashicorp__terraform-35611）在 Claude 侧判断写完前已开跑。
- 判断者输入只有事先冻结的 Sonnet 线索，看不到任何运行结果，信息上不可能泄漏；但按协议保守处理：**主分析用 72 道**，77 道作敏感性分析。DS/GLM 判断者同样按各自写完时间逐题判定。
