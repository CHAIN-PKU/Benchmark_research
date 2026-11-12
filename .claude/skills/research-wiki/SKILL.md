---
name: research-wiki
description: 本组的轻量研究 wiki：把论文、想法、实验、论断、踩坑经验各存一页 Markdown，用带类型的关系连起来，跨会话复用。开始新想法或新实验前先查，跑完实验、读完论文、踩完坑后记录。触发说法包括「记一下这个实验」「查查以前有没有踩过」「这个想法以前试过吗」「把这篇论文收进 wiki」「record this experiment」「search the wiki」。
---

# 研究 wiki

工具：`python3 <本 skill 目录>/scripts/wiki.py`，只用 Python 标准库。
数据目录：环境变量 `RESEARCH_WIKI_DIR`，或每条命令前加 `--root <目录>`。两个都没有时工具会报错退出；这时问用户数据放在哪，不要自己挑一个目录。数据可能含内部信息，不要放进公开仓库。

## 五种页面

| 类型 | 用途 |
|---|---|
| `paper` | 读过的论文：主张、方法、结果、局限、对我们有用的点 |
| `idea` | 研究想法，含失败的。失败原因要写清，避免以后重复尝试 |
| `experiment` | 一次实验：假设、设置（命令、commit、环境）、结果（数字 + 日志路径）、结论 |
| `claim` | 一条可检验的论断，及其证据状态 |
| `experience` | 踩过的坑：现象、根因、怎么发现的、以后怎么避免、证据 |

节点 id 写成 `类型:slug`，slug 就是文件名，例如 `experiment:2026-11-12-lr-sweep`。

## 命令

```sh
wiki.py init                                     # 建目录，已有内容不动
wiki.py new experiment 2026-11-12-lr-sweep "学习率扫描"   # 按模板建页，再用编辑工具填内容
wiki.py link idea:warmup tested_by experiment:2026-11-12-lr-sweep --note "一句话说明"
wiki.py show idea:warmup                         # 看页面和它的所有关系
wiki.py search "loss 发散"                       # 全文检索；不足 3 个字符的词用子串匹配
wiki.py lint                                     # 查断掉的关系、未知关系、重复关系；有问题退出码为 1
wiki.py index                                    # 重新生成 index.md
```

关系：`extends` `contradicts` `supersedes` `inspired_by` `tested_by` `supports` `invalidates` `learned_from` `related`。关系只存在 `graph/edges.jsonl`，不要在页面里手写。

## 什么时候用

- **开始一个新想法或新实验之前**：先 `search`，看以前有没有试过、踩过什么坑，把相关页 `show` 出来读完再动手。检索是按字面匹配的，整句话往往搜不到：拆成两三个关键词，再换几种说法各搜一次（比如「发散」「不收敛」「loss 爆了」）。按类型浏览就读 `index.md`。
- **实验跑完**：建 `experiment` 页，填数字和日志路径，再用 `supports` / `invalidates` 连到对应的想法或论断。
- **读完一篇论文**：建 `paper` 页；它启发了哪个想法，就用 `inspired_by` 连上。
- **踩坑花了超过 10 分钟**：建 `experience` 页，用 `learned_from` 连到出事的实验。

## 记录规矩

1. **贴原文，不转述**：报错、数字、命令照抄，写清楚日志或结果文件的路径。没有证据就写没有。
2. **不确定就标出来**：推测的根因写「推断，待确认」，之后证实了再改。
3. **临时故障不当长期事实**：网络断了、额度用完、某次服务报错，不要记成「某工具/某模型做不到 X」。这种话会在以后的会话里被反复引用，原因早已消失还在误导人。应该记的是：怎么修好的、缺了什么配置。
4. **失败的想法要留着**：这是防止重复踩坑最有价值的记录，状态写「失败」并写清原因。
5. **改完跑一次 `lint`**，有问题当场修。
