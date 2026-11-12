---
name: benchmark-pr-flow
description: >
  Benchmark_research 仓库的提交流程：从 main 拉分支、小步 commit、推远端、
  开 PR、按「只审一遍、只留必改」审查并合入。
  Triggers when: 要在 CHAIN-PKU/Benchmark_research 里改代码或文档、要提 PR、
  要审这个仓库的 PR，或用户问「benchmark 仓库怎么提改动」「PR 怎么开」。
  Do NOT trigger for: 其他仓库、纯本地实验脚本、与本仓库无关的 benchmark 论文调研。
metadata:
  dsh/owner: DSH agent
  dsh/repo: CHAIN-PKU/Benchmark_research
---

# Benchmark_research PR 流程（最小版）

## 前提

- 仓库走主干开发：`main` 是唯一主干，所有改动经分支 + PR 合入。
- 远端用 HTTPS：`https://github.com/CHAIN-PKU/Benchmark_research.git`。
- 本机凭证：`gh auth git-credential`（`gh auth setup-git` 已配好）。

## 一次改动的步骤

1. 同步主干：`git switch main && git pull --ff-only`。
2. 拉分支，名字带功能语义，例如 `feat/dsh-plugin-skill`。
   从 `main` 拉，不要从未合并的分支拉。
3. 只做能端到端验收的真实功能；一个 PR 一件事。
4. 本地至少验证一次：文档改动不跑检查；代码改动跑对应测试。
5. commit：一条 commit 说清为什么改，不写「update」这种空话。
6. `git push -u origin <branch>`，然后 `gh pr create --base main`。
7. PR 描述写：改了什么、怎么验证的、有什么已知风险。

## 审查规则（只审一遍）

- 只找真 bug 和必改项；不写假想问题。
- 输出格式：结论（能不能合）→ 必改 → 非阻塞建议。
- 开发和审查尽量换模型；同账号不能 approve 自己的 PR，留 comment。

## 合并前检查

- [ ] 分支从 `main` 拉出
- [ ] 本地验证做过，且结果写进 PR
- [ ] 没有夹带无关改动
- [ ] 审查意见只有「必改」项被要求处理
