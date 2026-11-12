# 本机开发运行手册（DSH 整理）

## 提交前必做

```sh
python3 ci/run.py                 # 本地 CI，五项全绿才推送
git config core.hooksPath .githooks   # 每个克隆执行一次，推送前自动跑 CI
```

## 技能装法

- Claude Code：把技能目录放 `.claude/skills/<name>/SKILL.md`。
- DSH：把同样的目录放进项目根的 `.dsh/skills/`（或 `~/.dsh/skills/`），自动发现、热更新，不用重启。

## 本机注意

- macOS 自带 bash 3.2，脚本别用 `declare -A` 等 bash 4+ 语法。
- 录屏、模拟按键需要系统权限；在 DSH 沙箱内跑的命令会被沙箱限制，需要时用一次性提权。
