## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
- `cmd/prometheus/main.go` 里所有 `queryEngine.Close()` 调用点：终止处理 goroutine（约 1048 行）、web 监听失败（约 1015 行）、web 配置校验失败（约 1024 行）。题面堆栈只指向一处，但另外两处在 agent 模式下同样会触发 nil 指针。
- `promql/engine.go` 的 `(*Engine).Close`（约 437 行）。它只判断了 `activeQueryTracker`，没有判断接收者本身。同文件的 `SetQueryLogger` 同样直接解引用 `ng`。决定修在调用方还是 `Close` 内部时，要考虑这两个方法是否应保持一致。
- `main.go` 的 `query_engine` reloader（约 908-926 行）已经用 `agentMode` 提前返回。可以参考它对 agent 模式的处理方式。
- `cfg.web.QueryEngine = queryEngine`（约 857 行）和 `web/web.go` 中使用 `h.queryEngine` 的地方（约 329、714 行）。agent 模式下它们拿到的也是 nil。这里主要看有没有同类的 nil 风险，不一定要改。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
- 对 nil `*Engine` 调用 `Close()`。
- 非 agent 模式下 `activeQueryTracker` 为 nil（比如没有配置 tracker）时，`Close()` 的行为。
- 非 agent 模式的正常关闭仍要正确关闭 `ActiveQueryTracker`，修复不能让它被跳过。

**C. 仓库里已有的约定、文档或测试**
- 查看 `promql/engine_test.go` 中与 `Close`、`ActiveQueryTracker` 相关的测试，确认现有语义。
- 查看 agent 模式相关的代码注释，例如 `// No-op in Agent mode.`，沿用其风格。
- 先在仓库里搜 `queryEngine` 和 `agentMode`，确认没有其他在 agent 模式下无保护使用 engine 的路径。

**D. 建议提交前额外自测的情况**
1. 以 `--agent` 启动，再发 SIGINT/SIGTERM，确认不 panic、正常退出。
2. 以 agent 模式启动，并让 web 监听失败（如端口被占用），确认错误路径同样不 panic。
3. 非 agent 模式正常启动后关闭，确认 `ActiveQueryTracker` 仍被关闭。
