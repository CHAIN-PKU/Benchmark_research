# 工具选品清单

日期：2026-11-12 · 作者：Claude Code（Claude Code 生态）、DSH（DeepSeek Harness 生态）· 状态：待陈润材确认

围绕 [路线图](roadmap.md) 挑选：每项都打开过仓库或文档页核实存在；没打开正文的标「未核」。星数是 2026-11-12 抓取时的数字。

## 已经有的（不用再装）

| 工具 | 在哪 | 用途 |
|---|---|---|
| 本地 CI | 仓库 `ci/`（PR #3） | 推送前查密钥、大文件、skill 格式、语法、测试 |
| research-wiki | 仓库 skill（PR #6）+ 数据在 DSH 的 `research-kb/` | 论文、想法、实验、踩坑共用笔记，两个 agent 都能读写 |
| ml-paper-writing、academic-plotting | 仓库 skill（PR #4） | 顶会写作规范、论文配图 |
| BenchJack | 仓库 skill（PR #4） | 审计 benchmark 能不能被刷分 |
| agent-team、neat-freak、session-wrap 等 | Claude Code 插件（Fomalhaut647） | 多会话分工、文档整理、收尾提交 |
| brooks-lint、Office 导出、多 agent 协作 | DSH 自带 | 代码审查、出报告和表格、并行调研 |

## 推荐加装

### 第一批：成本低、马上用得上

| 工具 | 大白话：是什么、为什么适合我们 | 代价 |
|---|---|---|
| [Context7](https://github.com/upstash/context7)（官方目录，约 65k 星） | 按需拉 PyTorch、transformers、datasets 等库的最新文档，避免 agent 照旧版 API 写代码 | 免费，建议申请免费 key 提高限额；要 Node 22.13+；只有 2 个工具，几乎不占上下文 |
| [arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server)（3.3k 星） | 搜 arXiv、分节读论文源码、导出 BibTeX。写相关工作、核实引用都要用 | 不需要 key；用 uvx 启动 |
| [Hugging Face 官方 MCP](https://huggingface.co/docs/hub/agents-mcp) + [huggingface/skills](https://github.com/huggingface/skills)（官方目录，11k 星） | 搜模型、数据集、论文；skill 里有本地跑评测（inspect-ai、lighteval）、处理数据集、后训练（trainer），一套覆盖评测、数据和后训练 | 需要 HF 账号；评测要模型 key |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai)（英国 AI 安全研究所，MIT） | 学 benchmark 基础设施的首选框架：一个任务就是「数据集 + 解题流程 + 判分器」，自带 200 多个现成评测，可以照着搭我们的第一道题 | pip 安装，要 Python 3.10+；沙箱要 Docker |

### 第二批：看组里用不用，或者等到对应阶段

| 工具 | 大白话 | 前提 |
|---|---|---|
| [Harbor](https://github.com/harbor-framework/harbor)（Terminal-Bench 团队，约 7k 星） | Terminal-Bench 2.0 的评测框架，在容器里批量、可复现地跑 agent。造 agent 类 benchmark 时照它的任务格式和沙箱结构 | 需要 Docker |
| [Weights & Biases MCP](https://github.com/wandb/wandb-mcp-server)（官方） | 用自然语言查 GPU 服务器上的实验结果、对比 run、写报告 | 组里用 W&B；要 API key |
| [Zotero MCP](https://github.com/54yyyu/zotero-mcp)（5.9k 星） | 搜本机 Zotero 文献库、读全文和批注 | 组里用 Zotero 7；工具多，需裁剪 |
| [OpenReview MCP](https://github.com/OpenCodice-Research/openreview-mcp) | 查 NeurIPS / ICLR 的审稿意见和录用结果，看审稿人常批评什么 | 项目很新，质量未核，先试 |
| [llm-wiki-plugin](https://github.com/praneybehl/llm-wiki-plugin)（官方目录） | 把 PDF、文章摄入成互相链接的 wiki，能查矛盾和过期内容 | 和 research-wiki 重叠，试用对比后再定 |
| [Jupyter MCP](https://github.com/datalayer/jupyter-mcp-server) | 让 agent 直接读、改、跑 notebook | 本机没有 GPU，只适合分析和画图 |
| lm-evaluation-harness | 静态题评测的事实标准，新题照它的配置格式写 | 只当参考，不是插件 |

### 暂不推荐

- **claude-mem 和各种云端记忆插件**：和 research-wiki 重复；有的会把研究笔记交给第三方服务。
- **向量检索（sqlite-vec、chromadb 等）**：现在条目少，关键词检索够用。等超过约 1000 条，或者换个说法就搜不到的情况出现 3 次以上，再上。
- **ARIS、claude-scholar、K-Dense**：耦合太重，已评估过。

## 本机要先补的底子

- **uv**：上面多数工具要 Python 3.10+，本机系统 Python 是 3.9。uv 自带新版 Python，统一用它启动，不动系统 Python。
- **Docker**（Docker Desktop 或 colima）：Inspect AI 沙箱和 Harbor 都要；本机现在没有。
- **账号**：HF 账号；W&B、Zotero 看组里是否在用。

## 没找到现成工具的

数据归因、数据合成：插件目录和网上都没有像样的现成插件，要自己写 skill（见路线图）。

## 待核

- DSH 的官方插件目录：列目录需要授权一次，还没列。
- Claude Code 格式的 skill 能否直接挂给 DSH：还没实测，拿 research-wiki 试一次。
- 插件目录里看起来相关、但没打开正文的：Research Desk、paper-review-system、bibtidy、Eval Conductor、DeepEval、Langfuse、FiftyOne 的 skill。
