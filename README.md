# Benchmark_research

CHAIN-PKU 的 Benchmark 研究开源仓库，由陈润材与科研 agent（Claude Code、DSH）共同维护。

## 仓库里有什么

| 路径 | 内容 |
|---|---|
| [docs/roadmap.md](docs/roadmap.md) | 路线图：benchmark 从选题到发表的八步，以及数据归因、数据合成、后训练怎么接上 |
| [docs/toolkit-shortlist.md](docs/toolkit-shortlist.md) | 工具选品：推荐加装的插件、MCP 和 skill |
| [docs/benchmark-frameworks.md](docs/benchmark-frameworks.md) | 造题框架参考：SWE-bench、Inspect AI、lm-evaluation-harness、BenchJack |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 开发规范（9 条） |
| `.claude/skills/` | Claude Code skill：research-wiki（研究笔记）、ml-paper-writing、academic-plotting、benchjack |
| `dsh-plugin/` | DSH 的 benchmark-pr-flow 技能 |
| `ci/`、`.githooks/` | 本地 CI 和推送前钩子 |
| `tests/` | 单元测试 |

## 协作方式

- 主干开发：`main` 是主干，改动走分支 + Pull Request 合入。
- 每个 PR 对应一个能端到端验收的真实功能，推送粒度宁大勿碎。
- 审查只审一遍，换一个模型来审。

## 本地 CI

push 和开 PR 之前，本地 CI 必须全绿：

```sh
git config core.hooksPath .githooks   # 每个克隆执行一次，之后每次 git push 前自动跑
python3 ci/run.py                      # 也可以手动跑
```

检查项：密钥泄露、超过 5 MB 的大文件、`SKILL.md` 缺 `name`/`description`、Python 语法错误，以及 `tests/` 下的 pytest。检查脚本本身只用 Python 标准库，几秒跑完；任何一项失败就拒绝推送，没有静默跳过。

仓库里有 `tests/` 时需要先装 pytest（`pip3 install pytest`），没装的话「单元测试」一项会失败、推送被拒。
