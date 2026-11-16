**档案：S3 GetObject 对空对象的后缀 Range（floci-io__floci-1142）**

**【1 题面要点】**
- 要求的行为：对已存在的 0 字节对象发 `Range: bytes=-1` 这类后缀范围请求，不应让读取失败。Trino 的 `TrinoInput.readTail(...)` 期望得到一次成功的空读取。
- 现状：返回 `416 InvalidRange`。题面说原因是 `S3Controller.handleRangeRequest` 在空对象上算出 `start = 0`、`end = -1`，然后拒绝了这个范围。
- 题面给了 aws cli 复现步骤，也给了 Trino 的 416 报错。
- 题面没有写期望的状态码（200 还是 206）、响应头和响应体。
- 题面没有给修法建议。题面写明"不引入新接口"。

**【2 相关代码】**
- `S3Controller.java:613-663` 的 `handleRangeRequest(S3Object, String, ResponseHeaderOverrides)` 是主要要改的地方。
  - 它把 `data.length` 存进 `int totalSize`。
  - 后缀分支在 629-635 行：`suffix = parseInt(after)`，`suffix<=0` 时返回 416，其余按 `start = max(0, total-suffix)`、`end = total-1` 计算。
  - 对空对象，这会得到 `start=0`、`end=-1`。
  - 644 行 `if (start < 0 || start >= totalSize || start > end)` 随即返回 416。
  - 648-662 行构造 206 响应，带 `Content-Range: bytes start-end/total`，并调用 `appendObjectHeaders(..., false)`，不带校验和。
- `S3Controller.java:665-679` 的 `invalidRangeResponse(int)` 生成 416 的 XML，带 `Content-Range: bytes */total`。
- `S3Controller.java:593-595` 是入口：`rangeHeader != null && startsWith("bytes=")` 时才进入 `handleRangeRequest`。非范围路径在 597-607 行，返回 200 并带 `Accept-Ranges`。
- 入口方法的 Range 参数在 548 行，通过 `@HeaderParam("Range")` 接收。

**【3 并列与牵连】**
- `S3Service.java:1137-1150`，`uploadPartCopy` 解析 `x-amz-copy-source-range`。它是另一套独立的范围解析，只支持 `start-end`。题面不涉及它，不必改。
- `headObject`（约 681-717 行）没有范围处理，不受影响。
- 全仓库只有 `handleRangeRequest` 这一个 GET 范围实现，没有并列副本。
- 改动只影响 `handleRangeRequest` 的所有调用者，也就是所有带 Range 的 GetObject。
- 要注意不能放宽非空对象的 416 行为。

**【4 现有测试与约定】**
- 测试在 `S3IntegrationTest.java`，用 RestAssured 并带 `@Order`。
  - 30-32 行：`bytes=0-4` 期望 206、`Content-Range: bytes 0-4/20`、`Content-Length: 5`。
  - `bytes=15-` 期望 `bytes 15-19/20`。
  - `bytes=-4` 期望 `bytes 16-19/20`。
  - 33 行 `bytes=50-100` 期望 416、`Content-Range: bytes */20`、body 含 `InvalidRange`。
  - 34-37 行：`bytes=0`、`bytes=-`、`bytes=abc-def`、`bytes=-1-4` 都期望 416。
- 现有测试里没有空对象的范围用例。隐藏测试很可能新增一个，比如创建空对象后发 `bytes=-1`。
- 外部规范：RFC 7233 里，后缀范围对零长度表示不可满足。真实 S3 对空对象的 `bytes=-N` 返回 200，是整个（空）对象。这和 RFC 不完全一致。真实 S3 的行为需要靠你的知识判断，仓库里没有写。
- 与题面的冲突：现有测试不冲突。这一点在仓库里没有查到明确约定。

**【5 边界与隐含要求】**
- 空对象的响应形态不确定：返回 200 空体，还是 206 加怪异的 `Content-Range`？按 RFC 格式，`bytes 0--1/0` 是非法的，所以不能走 206 的现有构造路径。
- 空对象加 `bytes=0-` 或 `bytes=0-0`，应该 416 还是 200？题面只提了后缀范围。
- `bytes=-0`：在 631 行 `suffix<=0` 会返回 416，空对象上这条路径是否保持不变也要定。
- 空对象响应应带 `Content-Length: 0`、`ETag`、`Accept-Ranges` 等头。走 200 分支时，这些头可以复用 597-607 行的逻辑。
- 空数据的 `copyOfRange(data, 0, 0)` 本身没问题，但 `end+1` 的算法要避开 `end = -1`。
- 非空对象的后缀范围大于对象长度时，现有行为是取整个对象，这要保持。
- 版本化对象、`response-*` 覆盖头：走 200 分支时要沿用 `appendObjectHeaders`。

**【6 改动规模】**
- 约 1 个主文件（`S3Controller.java`）、1 处函数内的局部修补，在 `handleRangeRequest` 里，可能加几行提前返回。
- 另需在 `S3IntegrationTest.java` 加 1-2 个测试，不涉及新增结构或多层改动。
- 如果选择返回 200，要抽出或复用 200 响应的构造。这会多几行，但没有贯穿多层。

**【7 难点一句话】**
代码修补本身很小；难点在于确定空对象后缀范围的正确响应（状态码、头、是否仅限后缀）。题面没有指定，隐藏测试的断言形态只能靠对真实 S3 行为的判断来猜，不能靠仓库里的约定。