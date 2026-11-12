# 来源

- 上游：https://github.com/benchjack/benchjack/tree/main/.claude/skills/benchjack
- 版本：commit 22c554f217357da5b3107c6e3fd7a128cef42d3b（2026-11-12 拉取）
- 许可证：Apache-2.0，见同目录 LICENSE
- 改动：删除了 SKILL.md frontmatter 里的 `allowed-tools` 一行。
  原配置会预先放行 bash、sh、pip、docker、mv 等命令，相当于完整 shell 权限；
  删除后，skill 执行的每条命令都照常走权限确认。其余内容原样保留。
- 改动 2：tools/run_bandit.sh 原本在缺 bandit 时会静默 `pip install`，改成提示安装命令后退出（码 1），不自动装依赖。
- 改动 3：tools/scan.sh 原本用 bash 4 的关联数组（declare -A），在 macOS 自带的 bash 3.2 上直接报错「declare: -A: invalid option」。改成每个工具一个 STATUS_<tool> 变量，汇总时用间接引用读取。（DSH 发现）
- 依赖：扫描需要 semgrep、bandit、hadolint，需要自己先装好。
