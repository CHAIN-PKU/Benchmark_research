我已经读完了 websocket 模块里的相关代码，下面直接给出档案。快照里没有 `pulsar-client-original`，所以 `MessageIdImpl.fromByteArray` 的实现没能直接读到，只能依据 issue 里的堆栈判断。

## 【1 题面要点】
- 期望行为：`messageId` 查询参数非法时，WebSocket reader 端点返回 HTTP 400，而不是 500。
- 复现有两种：
  - base64 里的 `+` 被解码成空格（`CJCj6QEQ UQwAA==`），导致 `IllegalArgumentException: Illegal base64 character 20`。
  - 任意非 base64 的字符串（`?messageId=invalidMessageId`），经 `MessageIdImpl.fromByteArray` 抛出 `IOException(IndexOutOfBounds)`。
- 题面没有给出期望的响应体。
- 修法线索（照抄）：
  - "`ReaderHandler.getMessageId()` performs no validation on the `messageId` query parameter…"
  - "`ReaderHandler`'s constructor … hardcodes `HttpServletResponse.SC_INTERNAL_SERVER_ERROR` … `ConsumerHandler` and `ProducerHandler` both call `AbstractWebSocketHandler.getErrorCode(e)` instead, which maps `IllegalArgumentException` to `SC_BAD_REQUEST`"。

## 【2 相关代码】
所在目录：`pulsar-websocket/src/main/java/org/apache/pulsar/websocket/`
- `ReaderHandler.java:388-398`，`getMessageId()`：
  - 处理 `earliest` / `latest` 两个特殊值。
  - 其余值走 `MessageIdImpl.fromByteArray(Base64.getDecoder().decode(...))`，没有任何校验。
  - 签名是 `throws IOException`。
- `ReaderHandler.java:~66-145`，构造函数：
  - `startMessageId(getMessageId())` 在 try 块内调用。
  - catch 里 `ReaderHandler.java:138` 硬编码 `response.sendError(SC_INTERNAL_SERVER_ERROR, "Failed to create reader: " + e.getMessage())`。
- `AbstractWebSocketHandler.java:182-204`，`getErrorCode(Exception)`：`IllegalArgumentException` 映射为 400，其余按类型映射，兜底 500。
- `AbstractWebSocketHandler.java:206-211`，`getErrorMessage`：`IllegalArgumentException` 对应 "Invalid query params: ..."，其他对应 "Failed to create producer/consumer: ..."。

## 【3 并列与牵连】
- `ConsumerHandler.java:154` 已经用了 `sendError(getErrorCode(e), getErrorMessage(e))`。`ProducerHandler.java:131` 也用 `getErrorCode`。这两处是参考实现，`ReaderHandler` 是唯一没跟上的。
- `ConsumerHandler.java:349` 和 `:368` 对 ack / negativeAck 命令里的 `command.messageId` 做 `Base64.getDecoder().decode` 加 `fromByteArray`，同样没有校验。这是并列的类似问题，但属于消息处理阶段，不是握手阶段，题面没有要求。
- 如果 `ReaderHandler` 改用 `getErrorCode`，所有进入该 catch 的异常的状态码都会变：
  - `ReaderHandler.java:118` 的 "Illegal Reader Type" 会从 500 变成 400。
  - 超时、topic 不存在、鉴权类异常会得到各自的码，不再统一是 500。
- 如果同时改用 `getErrorMessage`，响应体文案会变成 "Failed to create producer/consumer"，与 reader 语义不符，需要决定是否保留 "Failed to create reader"。

## 【4 现有测试与约定】
- `ReaderHandlerTest.java`：`testCreateIllegalReaderImp` 里用 `verify(servletUpgradeResponse, times(1)).sendError(anyInt(), anyString())`，只验证 `sendError` 被调用一次，状态码用 `anyInt()` 匹配，所以改状态码不会让它失败。
- `AbstractWebSocketHandlerTest.java` 和 `ProducerHandlerTest.java` 没有搜到 `getErrorCode` / `BAD_REQUEST` 的断言，没有现成的状态码测试可参照。
- 隐藏测试很可能是：
  - 构造 `ReaderHandler`，让 request 的 `messageId` 参数分别取 `invalidMessageId` 和带空格的 base64。
  - 用 `verify(response).sendError(eq(400), anyString())` 断言。
- 参考实现就是 Consumer/Producer 的 `getErrorCode` 模式，与题面期望一致，没有冲突。

## 【5 边界与隐含要求】
- 两类异常都要覆盖：`IllegalArgumentException`（base64 解码）和 `IOException`（`MessageIdImpl.fromByteArray` 解析失败）。
- 只改成 `getErrorCode` 不够：`IOException` 会落到 500。需要在 `getMessageId()` 里捕获 `IOException` 并转成 `IllegalArgumentException`，或者在构造函数里单独处理。
- `fromByteArray` 还可能抛出 `RuntimeException`，例如 `IndexOutOfBoundsException` 没被包装的情况。建议一并捕获。
- 合法 base64 但内容不是 MessageId 的情形，也应归为 400。
- `earliest` / `latest` 和空白值要保持原行为。
- 错误消息里不要把 messageId 原文带出去导致信息泄露或注入。
- 测试里 request 是 mock，`queryParams` 的获取方式要与构造流程配合。我没有读 `AbstractWebSocketHandler` 里 `queryParams` 的填充逻辑。

## 【6 改动规模】
- 只需改 `ReaderHandler.java` 一个文件，两处：`getMessageId()` 的异常转换，以及 catch 里的状态码。
- 另外要加测试。
- 属于局部修补，不用新增结构。

## 【7 难点一句话】
难点不在改动本身，而在容易漏掉第二类异常：只替换成 `getErrorCode(e)` 会让 `IOException` 仍然返回 500，必须把解码和解析失败统一转成 `IllegalArgumentException`。