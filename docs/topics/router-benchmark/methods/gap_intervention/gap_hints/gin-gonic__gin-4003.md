## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名但可能要一并处理的位置**
1. gin.go 中 `handleHTTPRequest` 的 HandleMethodNotAllowed 分支（约 690-708 行），`make([]string, 0, len(t)-1)` 的容量来自 `len(t)`。请确认没有路由树（`engine.trees` 为空）时这个容量是否会为负。
2. 同一分支里 `allowed` 之后的用法（`len(allowed)`、`strings.Join`、`engine.allNoMethod`）：修完后确认没有路由时仍会落到后面的 404 逻辑（`allNoRoute` / `serveError`）。
3. 仓库里其他对 `engine.trees` 做 `len(...)-1` 或类似容量计算的地方（可 grep `len(t)`、`len(engine.trees)`）。

**B. 题面没给例子但可能被检查的输入/边界**
1. 完全没有注册任何路由，且 HandleMethodNotAllowed=true，请求 "/" 与其他路径，应返回 404 而非 panic。
2. 只注册了一个方法的树（例如只有 GET），用同一方法请求不存在的路径：此时 `len(t)-1` 为 0，也要确认返回 404 且没有 Allow 头。
3. 注册了其他方法的树，请求方法本身没有对应的树（例如只注册了 POST，请求 GET）：应返回 405，且 Allow 头正确。

**C. 仓库已有约定 / 测试**
1. routes_test.go 的 `TestRouteNotAllowedEnabled`、`TestRouteNotAllowedEnabled2` 和 `TestEngineHandleMethodNotAllowedCornerCase`（约 773 行）：核对 405 + Allow 头的既有行为不变。
2. 如果用户自定义了 NoMethod/NoRoute 处理器，gin.go 的 `allNoMethod` / `allNoRoute` 约定也要保持。
3. 新测试可参考 routes_test.go 里现有的 NotAllowed 测试写法，用 `PerformRequest` 辅助函数。

**D. 提交前额外自测**
1. 题面的最小复现：`gin.New()` + HandleMethodNotAllowed=true，无路由，GET "/"，期望 404 且不 panic。
2. 同样的无路由情形下，再换 POST 等其他方法，以及注册了自定义 NoRoute 处理器，确认它被调用。
3. 运行 `go test ./...`，确认现有的 405 相关测试仍然通过。
