我查完了，现在整理档案。

## 【1 题面要点】
- 要求的行为：多技能工作区里，`waza check` 要像 `coverage` 和 `run` 一样找到对应的 eval。
  - `check skills/development/skill-creator` 应能找到 `evals/skill-creator/eval.yaml`，现在显示 `Evaluation Suite: Not Found`。
  - `check skill-creator` 应能按名字找到技能，现在报 `no SKILL.md found in <root>`。
- 题面给了复现步骤和目录结构。技能嵌套了两层（`skills/development/skill-creator`、`skills/copilot-exclusive/...`），`.waza.yaml` 里写了 `paths.skills: skills/`、`paths.evals: evals/`。
- 题面没有给期望输出的原文，只给了验收条件：
  - "`check` should discover the corresponding eval suite consistently"
  - "At minimum … locate the matching eval and report it, or explain the discovery rule clearly"
- 修法建议（四选一，都是可选项）：
  - "Make `check` reuse the same discovery logic as `coverage`"
  - 文档化解析规则
  - 加 debug 输出
  - 改进错误信息
- "Interface: No new interfaces"。隐藏测试大概率断言 `Evaluation Suite: Found`，也可能断言按名字能解析到嵌套技能。

## 【2 相关代码】
- `internal/workspace/workspace.go:80` `DetectContext`
  - 第 3 步用 `scanForSkills(skillsDir)` 扫技能目录。
  - `scanForSkills`（`:286`）只扫直接子目录，注释写明 "immediate child directories"，不递归。
  - 所以 `skills/development/skill-creator` 这类两层嵌套技能发现不了。这是 `check <name>` 报 "no SKILL.md found" 的根因：`FindSkill`（`:173`）找不到，没有技能时 `runCheck` 回退到当前目录（`cmd_check.go:196-210`），报错来自 `cmd_check.go:364`。
- `internal/workspace/workspace.go:187` `FindEval`
  - 优先级：`{root}/evals/{name}/eval.yaml`，然后 `{skillDir}/evals/eval.yaml`，然后 `{skillDir}/eval.yaml`。
  - 它先调 `FindSkill`，技能不在上下文里就直接报错。
- `cmd/waza/cmd_check.go:167-187`（路径参数分支）
  - 传 `checkReadiness(skillDir, nil)`，wsCtx 为 nil。
  - `checkReadiness`（`:358`、eval 部分 `:416-440`）的回退是 `workspace.DetectContext(wd)`，没带 `configDetectOptions()`，不用 `.waza.yaml` 的路径配置。
  - 因为技能嵌套，`FindEval` 又会因为技能不在上下文而失败；最后只剩 `skillDir/eval.yaml` 的同目录回退，所以找不到。
- `cmd/waza/workspace_resolve.go:13` `configDetectOptions`、`:46` `resolveWorkspace`
  - 前者读 `.waza.yaml` 的 skills/evals 路径，`run` 和 `eval` 等命令都用它。
  - `resolveWorkspace` 按名字解析技能，依赖 `DetectContext`。
- `internal/checks/eval_suite.go:26` `EvalSuiteChecker.Check`
  - 也用 `DetectContext(wd)`（无配置选项）加 `FindEval`，再回退同目录 `eval.yaml`。
  - 它是否参与 `check` 的输出，我没确认，要看 `cmd_check.go:902` 一带显示的是不是 `report.hasEval`。
- `internal/discovery/discovery.go:30` `Discover` 和 `:107` `findEvalConfig`
  - `coverage` 和 `run` 用的递归发现，用 `filepath.Walk` 找任意深度的 SKILL.md。
  - 技能名取目录名 `Base(dir)`。
  - 评测候选路径：`tests/`、`evals/`、同目录，以及 `Dir(Dir(skillDir))/evals/name/eval.yaml`。对嵌套三层的技能，最后这项算出来是 `skills/evals/name`，对不上，`coverage` 实际靠别的路径找到 eval（见下）。
- `cmd/waza/cmd_coverage.go:267`：`searchRoots` 从 `root/evals` 入手，和 `Discover` 是另一套独立逻辑。

## 【3 并列与牵连】
- 同时存在至少三套发现逻辑：`workspace.DetectContext/FindEval`、`discovery.Discover`、`cmd_coverage.go` 自己的扫描。`check` 属于第一套。
- 同样调用 `DetectContext(wd)` 而不带配置选项的地方：
  - `cmd_check.go:426`
  - `internal/checks/eval_suite.go:31`
  - `cmd/waza/dev/copilot.go:126`
  - `cmd/waza/tokens/count.go:98`、`tokens/profile.go:163`
  - 带配置的：`cmd_eval.go:120`、`tokens/check.go`、`suggest.go`、`dev/loop.go`。
- 如果改 `scanForSkills` 让它递归，所有用 `DetectContext` 的命令（`run`、`eval`、`tokens`、`new-task`、`init` 等）都会受影响。
  - 递归后技能列表变多，`check` 无参数时会检查更多技能。
  - 同名技能的去重行为也会变化。`mergeSkillsByName` 按名字去重。
  - 递归时要避开隐藏目录、`node_modules`。
- `LooksLikePath` 含 `/` 就走路径分支，所以 `check skills/development/skill-creator` 走 `checkReadiness(dir, nil)`，不经过 `resolveWorkspace`。

## 【4 现有测试与约定】
- `cmd/waza/cmd_check_workspace_test.go:123-147` `TestCheckCommand_WorkspaceWithSeparatedEval`：`skills/eval-test` 只有一层，`evals/eval-test/eval.yaml`，参数是名字，断言 `"Evaluation Suite: Found"`。没有嵌套的测试。
- `cmd/waza/cmd_check_test.go:54`（`Evaluation Suite:`）、`:148`（`no SKILL.md found`）、`:186`（Found）。其中 `:148` 的断言要注意别被改掉。
- `internal/workspace/workspace_test.go`：
  - `TestDetectContext_MultiSkillWithSkillsDir`（`:72`）
  - `TestFindEval_SeparatedConvention`（`:137`）
  - `TestFindEval_NestedSubdir`（`:159`）
  - `TestFindEval_PriorityOrder`（`:205`）
  - `TestFindEval_MixedLayouts`（`:283`）
  - `TestFindEval_SkillNotInContext`（`:339`）
  - 都只覆盖一层目录。若新增嵌套测试，大概率加在这里。
- `internal/discovery/discovery_test.go:74` `TestDiscoverNestedDirectories`：说明 `Discover` 本来就支持嵌套，与 `workspace` 的 "immediate children" 约定不一致。
- `internal/checks/eval_suite_test.go`：用空 `WorkDir`，只测同目录回退。
- 约定：`FindEval` 的注释写明优先级；`.waza.yaml` 里 `paths.skills` 和 `paths.evals` 决定目录。题面期望与现有约定不冲突，只是现有实现没覆盖嵌套。

## 【5 边界与隐含要求】
- 技能名取值不一致：`workspace` 用 frontmatter `name`（空则目录名），`Discover` 用目录名。如果嵌套技能的 frontmatter name 与目录名不同，`evals/<name>` 用哪个，题面没说。
- 绝对路径与相对路径（`.waza.yaml` 在父目录时 `cfg.Dir` 拼接）。`check` 在子目录运行时，`DetectContext` 的 Walk-up 逻辑会把技能目录当单技能上下文。
- 路径参数形式的 `check`（`skills/development/skill-creator`）需要把 wsCtx 推导出来，传给 `checkReadiness`，而不是 nil。
- Windows 路径分隔符与大小写（`samePath` 已有处理）。
- 嵌套深度、同名技能冲突（`skills/a/x` 与 `skills/b/x`）、`.github/skills` 合并。
- 找不到 eval 时给更清楚的提示或搜索路径（题面可选项，不是必须）。

## 【6 改动规模】
- 最小修补：
  - 改 `scanForSkills` 支持递归，约 1 个函数。
  - 让 `cmd_check.go` 路径分支和回退使用 `configDetectOptions()`，约 2–3 处。
  - 再加测试。
  - 合计 2–3 个文件、几处局部改动。
- 若按"复用 coverage 的发现逻辑"重构：要统一 `workspace`、`discovery`、`coverage` 三套逻辑，会贯穿多层，改动面大得多。

## 【7 难点一句话】
难点是看出根因有两层：一是 `scanForSkills` 只扫一层，所以嵌套技能找不到；二是 `check` 的路径分支和回退没带 `.waza.yaml` 配置。改成递归扫描时还要避免破坏其他共用 `DetectContext` 的命令和现有的去重、优先级行为。