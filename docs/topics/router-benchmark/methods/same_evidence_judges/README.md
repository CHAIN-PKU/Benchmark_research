# 同一份线索、不同判断者（旧题，2026-11-15）

做法：同一份 Sonnet 查到的线索（≤3 条），交给不同判断者只做判断（单轮、不读仓库）。另有「换线索」：DS / GLM 查的线索交给 Sonnet 判，Sonnet 查的线索交给 DS 判。
- 脚本：judge_reason.py（列因素+方向+分量+概率，组名 R_）、judge_rubric.py（加具体掂量规则，RB_）、judge_fewshot.py + fewshot_v1.md（加 6 个 Sonnet 示范，FS_，示范题不计分）。
- 题单 tasks.json；输出 out_judge/。

AUC（标签：tagging/tag_data.json，宽松口径「至少挂一次」；2026-11-16 统一重算）：

| 组 | 题数 | 挂 | AUC |
|---|---|---|---|
| R_sonnetEv_opus | 82 | 14 | 0.737 |
| R_sonnetEv_sonnet | 82 | 14 | 0.718 |
| R_sonnetEv_haiku | 81 | 14 | 0.607 |
| R_sonnetEv_ds | 78 | 14 | 0.555 |
| R_sonnetEv_glm | 81 | 14 | 0.552 |
| RB_sonnetEv_haiku（加规则） | 82 | 14 | 0.680 |
| FS_sonnetEv_haiku（加示范） | 76 | 11 | 0.627 |
| sonnetEv_sonnetJudge | 81 | 14 | 0.739 |
| sonnetEv_dsJudge（换判断者） | 76 | 13 | 0.548 |
| dsEv_sonnetJudge（换线索） | 80 | 14 | 0.696 |
| glmEv_sonnetJudge（换线索） | 70 | 13 | 0.685 |

注意：此前群里和文档里报过的同组数字（如 Sonnet 0.70、Opus 0.69、Haiku 0.60、DS 0.56、GLM 0.53；换线索 0.67/0.66/0.51）用的是另一份标签快照（主批归档），与本表略有出入；排序和结论不变。论文定稿时统一用一份冻结标签重算。
样本小（14 道挂），区间宽；新题上的复核见 prereg_judge_intervention。
