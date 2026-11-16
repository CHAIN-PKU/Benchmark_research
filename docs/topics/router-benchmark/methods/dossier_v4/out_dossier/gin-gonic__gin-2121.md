**档案：DataFromReader 在 extraHeaders 为 nil 时崩溃**

**【1 题面要点】**
- 要求的行为：`c.DataFromReader(..., nil)` 以及 `render.Reader{Headers: nil}` 都不应 panic，要正常返回 200，并带上 Content-Length。
- 复现：给了完整的 main.go，其中 `c.DataFromReader(http.StatusOK, 5, gin.MIMEHTML, strings.NewReader("1234\n"), nil)` 会触发 recovered panic 并返回 500。
- 期望输出：`HTTP/1.1 200 OK`。
- 修法建议（照抄）：在 `if r.ContentLength >= 0 {` 里加入 `if r.Headers == nil { r.Headers = make(map[string]string) }`，然后再写 `r.Headers["Content-Length"] = ...`。
- 附带的次要问题："why extra headers does not replace global headers here?" 指的是 `writeHeaders` 里 `if header.Get(k) == ""` 的判断。这只是提问，没有要求修改。

**【2 相关代码】**
- `render/reader.go:22-30`，`Reader.Render`。第 25 行 `r.Headers["Content-Length"] = ...` 对 nil map 写入，这是 panic 的根源。
  - `r` 是值接收者，所以给 `r.Headers` 赋值只改局部副本，不会影响调用方。
- `render/reader.go:38-45`，`writeHeaders`。遍历 headers，只有当 `w.Header().Get(k)==""` 时才 `Set`。遍历 nil map 是安全的。
- `render/reader.go:33-35`，`WriteContentType`，调用 `writeContentType`（`render/render.go:36-41`）。它同样采用"已有值就不覆盖"的策略。
- `context.go:913-920`，`DataFromReader`，直接把 `extraHeaders` 原样传给 `render.Reader.Headers`，没有做 nil 处理。

**【3 并列与牵连】**
- 只有 `Reader.Render` 一处写入 `Headers`。仓库里 `Headers` 只出现在 reader.go 和 render_test.go。
- 调用点：`context.go:914` 是生产代码里唯一的构造点。`render/render_test.go:500、523` 和 `context_test.go:1793` 是测试里的构造点。
- 没有并列的 Render 实现有同样的问题：Data 等其他渲染器没有 Headers 字段。
- 修在 `Render` 里（issue 的写法）就能同时覆盖 `Context.DataFromReader` 和直接使用 `render.Reader` 这两条路径。如果只在 `DataFromReader` 里修，直接构造 `Reader{}` 仍会 panic。
- 当前代码会把 `Content-Length` 写进调用方传入的 map。在 `Render` 里改写原 map 会污染调用方的数据，这是额外的牵连。
- README.md:1220-1235 的示例传了 extraHeaders，不受影响。

**【4 现有测试与约定】**
- `render/render_test.go:492-513`（`TestRenderReader`）：
  - 断言 `assert.Equal(t, strconv.Itoa(len(body)), w.Header().Get("Content-Length"))`。
  - 断言 `assert.Equal(t, headers["Content-Disposition"], w.Header().Get("Content-Disposition"))`。
  - 这些测试里 Headers 都非 nil。
- `render/render_test.go:515-536`（`TestRenderReaderNoContentLength`）：
  - 传入 `ContentLength: -1`。
  - 断言 `assert.NotContains(t, "Content-Length", w.Header())`。参数顺序写反了，这条断言基本无效。
- `context_test.go:1783-1800`（`TestContextRenderDataFromReader`）：extraHeaders 非 nil，断言 Content-Length 等于 `fmt.Sprintf("%d", contentLength)`。
- 没有任何 nil Headers 的测试，隐藏测试大概率就是补这一项。
- CHANGELOG.md:22 记录了"支持负的 Content-Length"（#1981），这是 `ContentLength >= 0` 判断的来源。负值时不应写 Content-Length 头。
- 约定上"已有 header 不覆盖"（`header.Get(k)==""`）与题面并不冲突。题面里的这个问题只是疑问。

**【5 边界与隐含要求】**
- `Headers == nil` 且 `ContentLength >= 0`：要写出 Content-Length，且不 panic。
- `Headers == nil` 且 `ContentLength < 0`：本来就不会 panic，也不应写 Content-Length。
- 复现里的场景：先用 `c.Writer.Header().Set("X-Extra-Header", ...)`，再 nil 调用，应当保留这个头。
- 隐含风险：如果为了避免改写调用方的 map 而拷贝一份，要保证行为不变。
- `writeHeaders` 的"不覆盖"语义：如果调用方的 Headers 里已经带了不同的 Content-Length，现有行为是被覆盖（第 25 行赋值），但 `writeHeaders` 对已设置的响应头又不覆盖。这个组合的结果不改变，没有必要动。
- 另一种可行的写法：不往 map 里写，直接 `w.Header().Set("Content-Length", ...)`，同样能避开 nil map 问题。

**【6 改动规模】**
- 生产代码：1 个文件（`render/reader.go`），约 3 行局部修补，没有新增结构，也不跨层。
- 测试：可能在 `render/render_test.go` 或 `context_test.go` 中新增 nil Headers 的用例。

**【7 难点一句话】**
这道题几乎没有难度：根因在 `render/reader.go:25` 对 nil map 的写入，题面已经给出了修法，唯一需要留意的是修在 `Render` 里而不是 `DataFromReader`，以便让两条调用路径都得到修复。