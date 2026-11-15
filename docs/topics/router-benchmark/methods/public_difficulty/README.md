# 同题他家公开成绩 → 预测 DS 成败（2026-11-16）

数据：SWE-bench/experiments `evaluation/multilingual` 下 14 份公开提交的 per_instance_details.json（mini-swe-agent，Claude 4.5/4.6、DeepSeek 3.2、Gemini 3、GLM-5、GPT-5.2、Kimi K2.5、MiniMax 2.5 等）。
与我们 192 道旧题重合 152 道（其余 40 道为 django/sphinx 等，不在 Multilingual）。
特征：13 家（去掉 DeepSeek 3.2）在该题上的未解决比例。

| 预测信号 | 宽松口径 AUC（挂 36） | 严格口径 AUC（挂 22） |
|---|---|---|
| 同题他家未解决比例（13 家） | **0.91**（0.85–0.96） | **0.955**（0.92–0.98） |
| 只用 DeepSeek 3.2 一家成败 | 0.78 | — |
| Sonnet 读仓库事前判断（同 146 道） | 0.61 | — |
| 两者平均 | 0.89 | — |
两者相关 0.40。括号为 2000 次重抽样 95% 区间。

读法：
1. DS 挂的题绝大多数是「大家都挂的难题」，不是 DS 独有的短板；题目难度是跨模型共享的。
2. 「历史没用」是用错了历史：仓库、话题层面的历史没信号，**同一道题上别家的结果**信号极强。
3. 局限：这个信号只在别人已经跑过这道题时存在；真正的新题（前瞻、SWE-rebench 新月份）一开始没有。它是「事前预测」的强参照/上限，也提示一条实用路线：先用便宜模型跑一次，再预测贵模型。
脚本：`analyze.py`（数据从上述公开仓库下载，未入库）。

## 补充：同一份 Sonnet 事前预测 → 14 家公开 AI 各自成败（146 道旧题）
与公开难度（14 家未解决比例）的秩相关 0.45。逐家 AUC：
Claude 4.5 Haiku 0.65 · Claude 4.5 Opus 0.69 · Claude 4.5 Sonnet 0.70 · Claude 4.6 Opus 0.62 · DeepSeek 3.2 0.76 · Gemini 3 Flash 0.70 · Gemini 3 Pro 0.68 · Gemini 3.5 Flash 0.72 · GLM-5 0.72 · GPT-5.2 high 0.64 · GPT-5.2 codex 0.61 · GPT-5 mini 0.73 · Kimi K2.5 0.68 · MiniMax 2.5 0.70。
注：公开提交统一用 mini-swe-agent，与我们的跑法不同。

## 与前瞻集的关系（重要）
前瞻 123 道中 114 道属于 SWE-bench Multilingual，已有这 14 家的公开逐题成绩：可做免费多目标评测，但不能算「无人跑过的新题」。SWE-rebench 2026-07 的 100 道与公开结果无重合，是唯一真正的新题集。
由于公开难度与 DS 成败高度相关（AUC 0.91），在 DS 揭晓前不得用公开成绩查看预注册 77 道的 A/B/C/D 分组表现。
