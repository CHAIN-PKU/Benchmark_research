# 跨模型预测员对照（crc 11-15 00:17：「不要只用 Claude 模型」）

目的：同 84 道、同一份代码快照、同一份清单（禁用记忆），只换「预测员」模型，比较准度（AUC）。
已有参照（Claude 子 agent 跑法）：Sonnet+清单 0.71、Opus+清单 0.69。

内容：snap/（84 份快照，无 git 历史）、issue/（题面）、checklist_nomem.md、tasks.json、run_predictor.py。
**本包不含答案标签**，跑完把 out/<tag>/ 交回 Claude Code 打分。

步骤（DSH）：
1. 冒烟：每个模型先跑 1 道 `--tasks fmt__fmt-3158`，看 out/<tag>/ 里出 json、无 err。
2. 正式：`python3 run_predictor.py <tag> --jobs 4`（tag 例：glm、kimi、ds、sonnet_ref）。
3. 每个模型通道用环境变量指定（ANTHROPIC_BASE_URL 等），令牌只放环境变量。
4. **建议加一组 sonnet_ref**：同一个运行器跑 Sonnet，保证跑法完全一致再比（原先 Claude 是 42 道一个会话，这里一题一会话）。

隔离：每题 HOME 为空目录（读不到长期记忆），工作目录是快照，禁网络工具和写工具。
