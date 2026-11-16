【1 题面要点】
- 要求的行为：`HandleMethodNotAllowed=true` 且没有注册任何路由时，`ServeHTTP` 不能 panic，应该返回 404。
- 复现：`gin.New()`，设 `g.HandleMethodNotAllowed = true`，对 `GET /` 调 `ServeHTTP`。
- 期望：“No crash. I would have instead expected an HTTP error response like a 404”。
- 实际：panic `makeslice: cap out of range`，栈指向 `handleHTTPRequest`。
- 题面没有给修法建议。

【2 相关代码】
- `gin.go:693`：`allowed := make([]string, 0, len(t)-1)`。这是根因。没有任何路由时 `len(t)==0`，容量为 -1，运行时 panic。
- `gin.go:646-712`：`handleHTTPRequest`。
  - 660-688 行按方法查树。
  - 690-708 行是 405 分支，先算 `allowed`，非空才返回 405。
  - 710-711 行兜底返回 404，走 `allNoRoute` 并调用 `serveError`。
- `gin.go:694`：遍历 `engine.trees`，对每个非当前方法的树调用 `getValue`，收集 `allowed`。
- `gin.go:212`：`trees` 初始为 `make(methodTrees, 0, 9)`，所以空 trees 是 `New()` 后的正常状态。

【3 并列与牵连】
- 全仓库只有 `gin.go:693` 一处 `len(t)-1`。
- 没有并列实现。`engine.trees` 的其他使用点有 `gin.go:290`、`368`、`495`，都是 `range` 或 `len>0` 判断，不受影响。
- 405 分支内部，下面几行没有越界风险：
  - 第 698 行用 `nil` params 调用 `getValue`，对 params 的使用已有保护。
  - 第 698 行传入 `c.skippedNodes`。
  - `getValue` 里的 `skippedNodes` 处理（`tree.go:444-446`）是对切片做 `[:index+1]`。`allocateContext` 在 `engine.maxSections==0` 时容量为 0，这一点不属于本题。
- 改动只影响 405 分支，不影响 404 或正常路由。

【4 现有测试与约定】
- `routes_test.go:492-505` `TestRouteNotAllowedEnabled`：注册 POST `/path`，GET 请求断言 `StatusMethodNotAllowed`。
- `routes_test.go:507-515` `TestRouteNotAllowedEnabled2`：断言 405。
- `routes_test.go:517-527` `TestRouteNotAllowedEnabled3`：断言 405，且 `Allow` 头包含 `GET` 和 `POST`。
- `routes_test.go:773-790` `TestEngineHandleMethodNotAllowedCornerCase`：用 `HandleMethodNotAllowed` 测一个边角用例，断言 404。
- 现有测试都至少注册了一条路由，没有覆盖“空 trees”的情况。
- 与题面期望不冲突。404 是原有兜底行为。
- `gin.go:691-692` 的注释引用 RFC 7231 §6.5.5：405 响应必须带 `Allow` 头。这一点修复后仍要保持。

【5 边界与隐含要求】
- 只注册了与请求相同方法的路由、没有其他方法的树时，`len(t)-1` 为 0，不会 panic，当前也返回 404。
- 修复后必须保持原有语义：
  - 有其他方法匹配时返回 405，并带 `Allow` 头。
  - 无匹配时返回 404。
  - 用户自定义的 `NoRoute` 仍然会被调用。
- 隐藏测试很可能在 `routes_test.go` 或 `gin_test.go` 里新增一个用例：空引擎加 `HandleMethodNotAllowed=true`，请求后断言 404。
- 若测试经 `PerformRequest` 调用，走的是 `ServeHTTP`，会经过 `engine.pool` 里的 `allocateContext`。`maxSections` 为 0 时容量为 0，当前路径不会访问这个切片。

【6 改动规模】
- 1 个文件、1 处修改，局部修补。
- 做法有两种：把容量改成 `max(len(t)-1, 0)`；或者直接用 `make([]string, 0, len(t))`。
- 另需在测试文件里加 1 个用例。

【7 难点一句话】
- 根因一眼可见，几乎没有难度。唯一要注意的是不要改变 405 的语义，包括 `Allow` 头。