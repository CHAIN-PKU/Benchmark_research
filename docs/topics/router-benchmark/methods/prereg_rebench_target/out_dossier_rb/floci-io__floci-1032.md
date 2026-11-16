**档案：API Gateway REST `_user_request_` 路径返回 404（"Invalid API id specified"）**

（以下均为我在仓库中查证所得。其中“根因是 region 解析”是我的推断，尚未运行复现。）

## 【1 题面要点】
- 要求的行为：创建 REST API、资源 `hello`、`AWS_PROXY` Lambda 集成并部署到 `dev` 阶段后，请求 `GET /restapis/$API_ID/dev/_user_request_/hello` 应转发到 Lambda 并返回其响应。
- 实际行为：返回 HTTP 404 `{"message":"Invalid API id specified"}`。
- 复现：题面给了完整的 aws cli 加 curl 步骤。
- 期望输出：只写了“Request routes through API Gateway to the Lambda function and returns the Lambda response.”
- 修法建议：没有。`Interface` 一节写的是 "No new interfaces are introduced."
- 关键线索，写在 Notes 和 Environment 里：
  - “The API is created successfully”，管理面操作都正常。
  - “Only the data plane invocation path fails”。
  - 区域是 **eu-west-2**，而 curl 请求没有带 SigV4 签名。
  - 版本是 Floci 1.5.16。

## 【2 相关代码】
- `ApiGatewayUserRequestController.java:16`：`@Path("/restapis/{apiId}/{stageName}/_user_request_")`。
  - 五个 HTTP 方法（GET/POST/PUT/DELETE/PATCH，:27-73）都委托给 `ApiGatewayExecuteController.dispatch(...)`。
  - 这个类本身没有 region 逻辑。
- `ApiGatewayExecuteController.java:226` 的 `dispatch`：
  - `:228` 用 `regionResolver.resolveRegion(headers)` 取 region。
  - `:233` 先查 v2 API。
  - `:246-247` 调 `getRestApi(region, apiId)` 和 `getStage(region, apiId, stageName)`。找不到时，用异常消息和 404 状态直接返回。
  - 之后的 `getResources` (:257)、鉴权、`invokeProxy` (:308/:327 `lambdaService.invoke(region, …)`) 都沿用同一个 region。
- `core/common/RegionResolver.java:37-50`：
  - 只从 `Authorization` 头里用正则 `Credential=\S+/\d{8}/([^/]+)/` 取 region。
  - 没有该头或不匹配时，返回配置的默认区域。
- `ApiGatewayService.java:189-192`：
  - `getRestApi` 用 `apiKey(region, apiId)` 查 `apiStore`，key 形如 `region::apiId`。
  - 查不到就抛 `NotFoundException "Invalid API id specified" 404`，与题面报错完全一致。
- **最可能的根因**：curl 请求没有 Authorization 头，region 回落到默认 `us-east-1`。而 API 是用 eu-west-2 的 CLI 创建的，存在 `eu-west-2::id` 下，所以查不到。`dispatch` 里没有“按 apiId 反查所属 region”的逻辑。
- 上述推断与现有测试吻合：`ApiGatewayUserRequestIntegrationTest` 创建和调用都不带 region 头，两边同为默认区域，所以通过。

## 【3 并列与牵连】
- 并列入口：`/execute-api/{apiId}/{stageName}`（`ApiGatewayExecuteController.java:59`）走同一个 `dispatch`，有同样的 region 问题。
  - 若修在 `dispatch`，两个入口会同时修好。
  - 若只改 `UserRequestController`，则不会。
- `ApiGatewayAwsExecuteController.java` 是另一个执行控制器，我没读。它可能有自己的 region 处理，需要核对是否同样受影响。
- `ApiGatewayCustomDomainFilter.java` 做自定义域名到 API 的映射，里面没有 `resolveRegion`，只有域名匹配。如果它转发到 execute 路径，也会受 region 影响。
- v2（HTTP API）分支：
  - `dispatch` 在 `:233` 用 `apiGatewayV2Service.getApi(region, apiId)` 判断是 v1 还是 v2，同样依赖 region。
  - 如果 region 错了，v2 API 会被当作不存在，落入 v1 分支再报 404。
- `dispatchV2` 与各 `invoke*` 方法都接收 `region` 参数，所以“正确 region”需要在 `dispatch` 入口一次性确定，下游不用改。
- 管理面 `ApiGatewayController` 约 100 处 `resolveRegion(headers)`，这是 AWS CLI 带签名所以没问题，不需要改。

## 【4 现有测试与约定】
- `ApiGatewayUserRequestIntegrationTest.java:104-111`：
  - `.get("/restapis/" + apiId + "/prod/_user_request_/hello")` 期望 `statusCode(200)` 且 `body("message", equalTo("ok"))`。
  - 使用 MOCK 集成，不带 Authorization，不设 region。
  - `:113-120`：`/execute-api/{apiId}/prod/hello` 同样期望 200。
  - `:124`：清理用 `delete("/restapis/" + apiId)`，期望 202。
- `ApiGatewayExecuteControllerTest.java` 和 `ApiGatewayProxyMatchTest.java` 是单元测试。我没读，不知道它们是否构造 `RegionResolver`、是否会因改动签名而受影响。
- 仓库测试里没有任何一处在调用时指定非默认 region 的头；我搜 "Authorization|eu-west|region" 只命中授权器用例（`Bearer ...`）。
- 约定与规范：
  - `docs/services/api-gateway.md:100` 给的示例是 `curl http://localhost:4566/restapis/$API_ID/dev/_user_request_/users`，同样没有签名。
  - 这与题面期望一致，不冲突。
  - 真实 AWS 的 execute-api 域名里带 region，但本地仿真的路径里没有，所以必须靠 apiId 反查。
  - `CHANGELOG.md:519` 记录了 `_user_request_` 是为兼容 LocalStack 加的。LocalStack 的该路径也无需签名。
- 隐藏测试很可能是：用 `Authorization` 头里带非默认 region（如 eu-west-2）来创建，然后不带头或带别的 region 来调用，断言 200。

## 【5 边界与隐含要求】
- 请求带的 region 与 API 所在 region 不同，或完全没带 Authorization：应按 apiId 找到真正所在的 region。
- 带了正确 region 的请求，行为应不变（优先使用请求 region、再回退查找，或反之，二选一并保持一致）。
- 不同 region 下可能存在相同的 apiId（概率很低，apiId 随机生成），需要决定取哪个。
- 找不到 API 时仍要返回 404 且消息不变（现有行为）。
- v2 HTTP API 的探测（`:233`）需要用同一个反查后的 region。
- 反查之后，下游 `lambdaService.invoke(region, functionName, …)` 要用哪个 region：
  - API 的 region，还是集成 URI/ARN 里的 region（题面里两者都是 eu-west-2）？
  - Lambda 函数在 eu-west-2 创建，所以必须用该 region，否则会报 "Function not found"。
- 授权器、API key、usage plan 都按 region 查（`:276`、`:352`、`:555`），需要同一个 region。
- `buildProxyEvent` 里的 ARN 和 requestContext 用的也是这个 region (:615)。
- 题面里 Lambda 用的是 S3 代码包。我没确认此类函数是否能在测试里被调用，但这属于 Lambda 服务，不是本题改动范围。

## 【6 改动规模】
- 预计 1-2 个文件、几处：核心是 `ApiGatewayExecuteController.dispatch` 开头的 region 确定逻辑。
- 可能需要给 `ApiGatewayService`（和 `ApiGatewayV2Service`）加一个“按 apiId 反查 region”的小方法，用 `apiStore.scan` 扫描 `k.endsWith("::" + apiId)`。服务里已有类似写法（`:751`、`:843` 对域名的 `scan(k -> k.endsWith("::" + domainName))`）。
- 属于局部修补，不需要新增分层。
- 另外要加一个集成测试，覆盖“非默认 region 创建、无头调用”。

## 【7 难点一句话】
难点在于**定位根因**：404 消息看起来像路由或 API 不存在，实际是数据面请求没有签名头，导致 region 回落到默认值，而管理面是带 region 创建的。修复要决定“region 到底以谁为准”，并保证 v1/v2、授权器和 Lambda 调用都用同一个 region。题面没给任何提示，修复本身代码量很小。