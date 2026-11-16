**档案：axios 响应 `Content-Encoding` 大小写问题**

**【1 题面要点】**
- 要求的行为：响应头 `content-encoding` 的值应大小写不敏感。服务端（如 storage.googleapis.com）返回 `GZIP`、`Gzip`、`GZip` 时，axios 应照常解压。
- 现状：值为 `GZIP` 时 axios 不解压。
- 复现：没有代码片段。只写了"任何 content-encoding 值非全小写的压缩响应"。
- 期望输出：该节写的是 "_No response_"。
- 修法建议：没有。题面只说 "header value should be case-insensitive"。
- 版本：axios 1.5.0，http 适配器，Node 18。

**【2 相关代码】**
- `lib/adapters/http.js:438` 的 `handleResponse` 回调是唯一相关的位置。
- `:467`：`if (config.decompress !== false && res.headers['content-encoding'])`，判断是否需要解压。
- `:470-472`：HEAD 请求或 204 响应时删除该头。
- `:474-500`：`switch (res.headers['content-encoding'])` 直接用原始值做严格匹配。
  - `'gzip'`、`'x-gzip'`、`'compress'`、`'x-compress'`：推入 `zlib.createUnzip`。
  - `'deflate'`：先推入 `ZlibHeaderTransformStream`，再推入 `createUnzip`。
  - `'br'`：仅在 `isBrotliSupported` 时推入 `createBrotliDecompress`。
- 匹配成功后，各分支都会 `delete res.headers['content-encoding']`。
- 非全小写的值落不进任何 case，也没有 default。结果是既不解压，头也保留。

**【3 并列与牵连】**
- 同一个 switch 里有 4 组并列 case，都需要同样的归一化。只要在 switch 前统一转小写，就能一次覆盖。
- `res.headers['content-encoding']` 在 `:467`、`:474` 读取了两次，另有 `:471` 等处的 delete。如果只改 switch 的判断值，其他位置不受影响。
- `lib/adapters/xhr.js` 和 fetch 由浏览器自动解压，不涉及此问题。
- 我在 `lib/` 里搜了 `toLowerCase`，http.js 中没有对头值做过归一化。
- 解压后 `response.headers` 由 `new AxiosHeaders(res.headers)`（`:513`）构造。头已被删除，所以不会受影响。
- 影响面：只改变"之前不解压"的大小写变体的行为。小写值的行为不变。

**【4 现有测试与约定】**
- 测试在 `test/unit/adapters/http.js:459-589` 的 `describe('compression')`。
  - `:471`：`res.setHeader('Content-Encoding', 'gzip')`，随后断言 `assert.deepEqual(res.data, data)`。
  - `:515-586`：`algorithms` 块对 gzip、compress、deflate、deflate-raw、br 做循环。
    - 测试设的头值是 `type = typeName.split('-')[0]`，全是小写。
    - 断言是 `assert.strictEqual(data, responseBody)`。
    - 空响应用例（Z_BUF_ERROR）也覆盖了这些类型。
  - `:494-513`：`decompress: false` 时保持原始压缩数据。
- 现有测试里没有任何大小写变体的用例。
- 外部规范：RFC 9110 规定 content-coding 值大小写不敏感。这与题面期望一致，没有冲突。
- 仓库里没有对应的约定或参考实现。
- 隐藏测试很可能在这个测试文件里增加大小写变体，例如把 `'GZIP'` 之类的值设进头，再断言能解压。

**【5 边界与隐含要求】**
- 所有分支都应不区分大小写，包括 `x-gzip`、`compress`、`deflate`、`br`。
- 头值可能带空白，规范上也可能是逗号分隔的列表。题面没提，大概率不需要处理。
- 归一化应保证后续的 `delete res.headers['content-encoding']` 仍然生效。`res.headers` 的键由 Node 保证为小写，所以键名不是问题。
- `decompress: false` 时仍须原样保留，不能改写头值。
- HEAD 和 204 的分支行为保持不变。

**【6 改动规模】**
- 改 1 个文件（`lib/adapters/http.js`），1 到 2 处。
- 做法是在 switch 前取小写值，再用它来 switch。
- 属于局部补丁，不需要新增结构，也不需要贯穿多层。
- 另外可在测试文件里补用例。

**【7 难点一句话】**
难点不在实现。修法是单点、机械的小写归一化，几乎没有难度。唯一的风险是漏改其中一处读取。