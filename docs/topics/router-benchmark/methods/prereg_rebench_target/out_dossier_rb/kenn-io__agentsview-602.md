# 仓库档案：深层 workflow 子代理转录未被发现

（说明：issue 里写的 `DiscoverClaudeSessions` 在仓库里实际叫 `DiscoverClaudeProjects`。）

## 【1 题面要点】
- 期望行为：位于 `<project>/<session>/subagents/workflows/<wf_id>/agent-<id>.jsonl` 的转录要像一层目录下的 `subagents/agent-<id>.jsonl` 一样被发现、导入。
- 题面没给复现命令，也没给期望输出。只给了现象：一个会话下 312 个文件全部被丢弃。
- 建议修法（原句）：
  - "walk `subagents/` recursively (or specifically also descend into `subagents/workflows/<wf_id>/`)"
  - "treat `agent-*.jsonl` found anywhere beneath it the same way"
- `.meta.json`（`agentType: workflow-subagent`）只是"如果值得在 UI 展示"的可选项。"No new interfaces are introduced"，所以不改函数签名。

## 【2 相关代码】
- `internal/parser/discovery.go:310` `DiscoverClaudeProjects`
  - 遍历 `projectsDir` 下的项目目录。
  - 第 328-345 行收集顶层 `*.jsonl`，并排除 `agent-` 前缀。
  - 第 347-376 行扫描 `<session>/subagents`，用 `ReadDir` 只读一层。
  - 第 360 行 `if sub.IsDir() { continue }` 就是 bug 所在。
  - 最后按 Path 排序。
- `internal/parser/discovery.go:435` `FindClaudeSourceFile`
  - 按 session ID 反查文件。
  - 第 462-487 行对 `agent-` ID 只拼 `projDir/<sess>/subagents/<target>`，同样只看一层。
- `internal/sync/engine.go:462-502`（`classifyOnePath`）
  - 用于文件监听（watcher）和单文件同步时判断路径归属。
  - 第 488 行 `len(parts)==4 && parts[2]=="subagents"` 把路径深度写死为 4。
  - 对 `workflows/<wf>/agent-x.jsonl`，parts 长度是 6，会返回不匹配。
  - 所以即使全量发现修好了，增量同步也会漏掉这些文件。
- `internal/sync/engine.go:5590`
  - 这是 WorkBuddy 的项目推导，不是 Claude 的。
- `internal/parser/claude.go:212-219`
  - 父会话 ID 取自首个 `sessionId` 字段，不来自路径。
  - 深层文件只要里面的 `sessionId` 指向父会话，`parent_session_id` 就会正确。
  - 如果 workflow 转录里的 `sessionId` 等于自身，或缺失，就会没有父会话。这一点我没验证。
- `internal/parser/claude.go:881` 和 `:164-178`
  - 用 `toolUseResult.agentId` 把 `agent-<id>` 关联到父会话的 tool call。

## 【3 并列与牵连】
- 三处需要同步修改，层级假设一致：`DiscoverClaudeProjects`、`FindClaudeSourceFile`、`classifyOnePath`。
- 容易漏的是 `classifyOnePath`，它走 watcher 路径。
- 同样写死 `subagents` 一层的还有 WorkBuddy（`internal/parser/workbuddy.go:52-62`、`:100`、`:123`、`:278`；`engine.go:726`）。它的转录格式不同，题面也没提，一般不该动。
- Cursor 的 `subagents` 另成一套（`discovery_test.go:1107`）。
- `DiscoverClaudeProjects` 已注册到 `types.go:78-79` 的 `DiscoverFunc` 和 `FindSourceFunc`，改动会影响所有走 Claude 注册项的调用。
- 其他影响：
  - 非 `agent-` 前缀的文件仍要排除（见 `discovery_test.go:86` 的 `not-agent.jsonl`）。
  - 会话总数会大幅增加。
  - `.meta.json` 不是 `.jsonl`，会被后缀过滤掉。

## 【4 现有测试与约定】
- `discovery_test.go:81-93` "Subagents" 用例：
  - 放入 `subagents/agent-abc.jsonl`、`agent-def.jsonl` 和 `not-agent.jsonl`。
  - 期望只得到 `agent-abc.jsonl`、`agent-def.jsonl`，加上父会话。
  - 第 109-113 行断言 `f.Project == "project-a"`。
- `discovery_test.go:230-237` `FindClaudeSourceFile` 的 "Subagent" 用例：`targetID "agent-sub1"` → `project-a/parent-sess/subagents/agent-sub1.jsonl`。
- `engine_integration_test.go:2086-2121`：
  - 断言 `TotalSessions:2`。
  - 断言 `ParentSessionID == "parent-uuid"`。
  - 断言 `FindSourceFile("agent-worker1")` 非空。
  - 第 2280-2295 行断言 `subagents/not-agent.jsonl` 被拒绝。
- 与题面期望不冲突。隐藏测试大概率是在上述测试旁增加 `workflows/<wf>/agent-*.jsonl` 的用例，覆盖发现、查找和 sync。

## 【5 边界与隐含要求】
- 排序要保持稳定（按 Path 排序）。
- Project 要取顶层目录名，不能取 `workflows` 或 `wf_id`。
- 同一目录下的非 `agent-` 文件、`.meta.json` 要排除。
- 递归深度：`wf_id` 目录可能是任意名字，递归应能容忍。
- 符号链接：顶层用 `isDirOrSymlink` 处理，递归时是否跟随符号链接是个隐含决策。
- 不同 workflow 目录下的 agent ID 理论上可能重名。`FindClaudeSourceFile` 只返回第一个匹配。
- 增量同步里 `classifyOnePath` 需要接受深层路径，同时仍要拒绝 `parts[2] != "subagents"` 的无关路径。
- 父会话链接依赖文件内 `sessionId`，需要确认深层文件的该字段。
- 同步时要为深层文件正确推导 project（见 `engine.go:5570` 一带按 Agent 类型推导 project 的 switch）。我只看到其他 agent 的分支，没有看到 Claude 的，没有进一步核实。

## 【6 改动规模】
- 约 2 个源文件：`discovery.go` 和 `engine.go`。
- 3 处局部修补：发现循环、查找循环、路径分类。
- 不需要新结构，也不贯穿多层。
- 可选改动：`.meta.json` 和 UI 里的 workflow 分组，题面不要求。

## 【7 难点一句话】
discovery 改成递归本身很简单，难点是别漏掉并列的 `FindClaudeSourceFile` 和 `engine.go:488` 的写死深度，并且让深层文件的 Project 与父会话关联仍然正确。