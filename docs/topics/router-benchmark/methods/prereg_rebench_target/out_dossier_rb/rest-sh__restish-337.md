**档案：restish #337（204 且带 `Content-Encoding: gzip` 时报 EOF）**

**【1 题面要点】**
- 期望行为：服务器返回 204 No Content，且头里带 `Content-Encoding: gzip`、body 为空时，restish 应当正常成功，不报错。
- 复现：只有 Synadia 的 `DELETE` 日志，没有最小复现。
- 期望输出：没有明确写，只说 "it's expected to have an empty body"。
- 修法建议：没有。
- 关键报错：`ERROR: Parse response error` / `Caught error: EOF`，日志里有 `Decoding response from gzip`。
- 日志里的栈和文件名（`cli/request.go`、`cli/cli.go`）是旧版代码的。当前快照是重写后的 v2（模块 `github.com/rest-sh/restish/v2`，代码在 `internal/`），栈不能直接对应。
- 题面说 "No new interfaces"，所以不新增公开接口。

**【2 相关代码】**
- `internal/content/defaults.go:262-266`：gzip 编码注册，`Decompress: defaultGzipDecompress`。
- `internal/content/registry.go:412-415`：`defaultGzipDecompress` 直接调用 `gzip.NewReader(r)`。
  - 读 gzip 头时，空输入会返回 `io.EOF`。这就是最可能的根因：gzip 对空 body 构造 reader 就失败。
  - brotli（408）和 deflate（419-426）没有这个构造期失败的问题。deflate 用 `Peek(2)`，空输入时 err 非 nil，会退到 `flate.NewReader`，读取时才可能报错。
- `internal/content/registry.go:302-312`：`Registry.Decompress`，分发到各编码的实现。
- `internal/output/response.go:81-107`：`decodeBody`，先 `reg.Decompress(...)`，失败就返回 `"decompressing response: %w"`，这时 `len(raw)==0` 的短路（97-99 行）还没走到。主路径 `Normalize`（40 行）经它调用。
- `internal/cli/http.go:660-682`：`rawResponseBodyBytes`，同样先 Decompress，错误包成 "decompressing response"。
- `internal/cli/http.go:684-700`：`decompressedResponseBody`，直接返回 Decompress 的错误。

**【3 并列与牵连】**
- 上面三个调用点（`response.go:83`、`http.go:667`、`http.go:689`）都有同样的问题。
- 如果只在调用方处理（例如状态码是 204/304、`ContentLength==0` 或 HEAD 时跳过解压），三处都要改。
- 如果在 `defaultGzipDecompress` / `Decompress` 里处理空输入（先 `Peek` 一个字节，空则返回空 reader），一处就能覆盖所有调用方。
- 隐患：`bufio.Peek` 包装后要保证 `Close` 仍然正确。
- 修改 `Decompress` 会影响所有使用方，包括 `internal/cli/http.go` 的流式路径。
- 题面栈里的 `Operation.command` 对应生成命令路径，generic verbs 也走同一个 Normalize，所以不必另改。

**【4 现有测试与约定】**
- `internal/content/registry_test.go:333-352`：`TestGzipDecompression`，断言 `reg.Decompress("gzip", &buf)` 无错且解压结果为 `{"compressed":true}`。
- `registry_test.go:354-398`：`TestBuiltInDecompressors`，覆盖 gzip/deflate/br，断言解出 "hello world"。
- `registry_test.go:400-418`：deflate 接受 zlib 包装。
- `registry_test.go:426-`：identity 直通。
- 这些测试都没有测空 body 或 204。
- `internal/output` 下没有 Content-Encoding 相关测试（grep 为空）。
- `response.go:97-99` 已有约定：空 body 返回 `nil, nil, nil`。所以正确行为是 Body 为 nil、Raw 为空、不报错，与题面不冲突。
- `internal/cli/generated_test.go:3607` 有 `WriteHeader(http.StatusNoContent)` 的测试服务器，可作为 CLI 级测试的参考。
- 隐藏测试很可能在 `registry_test.go`（`Decompress("gzip", 空 reader)` 再 `ReadAll` 得到空）、`output` 的 Normalize 测试（204 + gzip 头），或 cli 测试。
- 三个层面的测试都有可能，所以修在最底层（Decompress）最稳。

**【5 边界与隐含要求】**
- 空 body 配 gzip/deflate/br 都要正常处理，不止 gzip。
- 204 以外也有空 body 带编码头的情况，比如 HEAD、304、200 且长度为 0。
- 不能吞掉真实的损坏 gzip 错误：非空但头损坏的输入仍要报错。
- 只有 1 个字节的截断输入，应保持报错（`Peek` 到一个字节但头不完整）。
- Normalize 之后 `Body == nil`、`Raw` 为空，下游格式化器要能处理，输出只显示状态行和头。
- 流式、raw 路径（`rawResponseBodyBytes`、`decompressedResponseBody`）也要不报错。
- `Close` 要正确关闭原始 body。

**【6 改动规模】**
- 小：核心改动是 `registry.go` 里 1 个函数，约 5–15 行，加几个测试。
- 如果选择在调用点处理，则是 3 处。
- 局部修补，不需要新增结构。

**【7 难点一句话】**
定位不难（`gzip.NewReader` 对空输入返回 EOF），难点在于隐藏测试会在哪一层断言（Decompress、Normalize 还是 CLI），以及修复要覆盖三个调用点和 br/deflate，同时不掩盖真实的 gzip 损坏错误。