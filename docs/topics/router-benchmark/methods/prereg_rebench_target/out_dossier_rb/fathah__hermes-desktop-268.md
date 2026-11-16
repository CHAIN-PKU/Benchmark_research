**Hermes Desktop 远程模式连接失败：仓库档案**

**【1 题面要点】**
- 要求的行为：远程模式应能直接对接已运行的 Hermes API server（`127.0.0.1:8642`），URL 带不带 `/v1` 都能用。题面也要求选了远程模式后，不再去启动 `~/.hermes/hermes-agent/...` 的本地网关。
- 复现：题面给了环境和 curl 结果，没有可执行的最小复现。
- 期望输出：题面写的是 "It should then list the exposed remote model: hermes-agent and send chat requests through the existing Hermes API server."。
- 修法：题面没有给，只提了 4 个问题：
  - 该用哪种 URL 格式？
  - 用哪个端点做校验？
  - 远程模式能否不依赖 `/models`、`/api/health`、`/cron`？
  - 能否不再 spawn 本地安装？
- 路由事实：`/health`、`/v1/health`、`/v1/models`、`/v1/chat/completions` 都返回 200；`/models`、`/api/health` 返回 404。
- 报错：
  - 填 `…:8642/v1` 时，聊天报 `API server returned 404: 404: Not Found`。
  - `[CRON] remote list failed: HTTP 404`。
  - `spawn …/venv/bin/python ENOENT`。
  - `ECONNREFUSED`。

**【2 相关代码】**
- `src/main/hermes.ts:31-42` `getApiUrl()`：远程模式只去掉末尾 `/`，不处理 `/v1` 后缀。这是 `/v1` 场景的主要根因。
- `src/main/hermes.ts:432` 和 `:322`：聊天和 `probeRealError` 都拼接 `${getApiUrl()}/v1/chat/completions`。URL 带 `/v1` 时变成 `/v1/v1/chat/completions`，返回 404。
- `src/main/hermes.ts:971-996` `testRemoteConnection`：请求 `${url}/health`，只认 200。填 `…/v1` 时请求 `/v1/health`，碰巧返回 200。校验通过了，聊天却失败，所以题面说"不可靠"。
- `src/main/hermes.ts:78-87` `resolveRemoteApiKey`：按 `stripTrailingSlashes` 比较 URL，决定是否复用已存的 key。
- `src/main/hermes.ts:130-149` `isApiServerReady`：用 `${getApiUrl()}/health` 探测。
- `src/main/cronjobs.ts:64-73` `remoteFetch`：用 `${getApiUrl()}/api/jobs`，远程模式下 `isRemoteMode()` 为真时走这里（`:92`、`:183`、`:222`、`:262-282`）。URL 带 `/v1` 时是 `/v1/api/jobs`，返回 404。若服务端本身没有 `/api/jobs`，也会 404，题面没法区分这两种情况。
- 本地网关的 spawn：
  - `src/main/hermes.ts:861-889` `startGateway`：用 `HERMES_PYTHON` 加 `HERMES_REPO` spawn。
  - `src/main/index.ts:612-613` 的 `send-message` 已有 `!isRemoteMode()` 守卫。
  - `src/main/index.ts:726` 的 `start-gateway` 在非 ssh 时无条件调用 `startGateway()`，没有远程判断。
  - `src/main/index.ts:424`、`:498`、`:761` 的 `restartGateway` 只靠 `isGatewayRunning()` 判断。
  - `src/main/hermes.ts:998-1004` `restartGateway`：`!gatewayStartedByApp && !isGatewayRunning()` 才返回，其余情况都会 `startGateway`。
- UI：
  - `src/renderer/src/screens/Welcome/Welcome.tsx:49-70` `handleConnectRemote` 调用 `testRemoteConnection`，失败显示 "Could not reach Hermes at this URL..."。
  - `src/renderer/src/App.tsx:50-55` 启动时再校验一次。
  - `src/renderer/src/screens/Gateway/Gateway.tsx:49` 调用 `startGateway`。
- 提示文案：`src/shared/i18n/locales/en/settings.ts:84-85` 写着 "must expose /health and /v1/chat/completions"，其他 locale 另有各自的 `remoteUrlHint`。

**【3 并列与牵连】**
- 所有用 `getApiUrl()` 的调用点都受 URL 规范化影响：
  - `hermes.ts` 的 `:132`、`:322`、`:432`。
  - `cronjobs.ts:72`。
  - ssh 模式的 `getSshTunnelUrl`，ssh 的 URL 不带 `/v1`，改动时别误伤。
- `testRemoteConnection` 和 `resolveRemoteApiKey` 里各有一套 `stripTrailingSlashes`，需要用同一套规范化，否则 key 复用的 URL 比较会失配。
- `config.ts:96-101` `resolveConnectionApiKeyUpdate` 也比较 `remoteUrl`。若保存时做规范化（如去掉 `/v1`），这里的比较要同步，否则测试里的 `https://hermes.example` 之类断言可能变。
- `installer.ts:301` `checkInstallStatus` 在远程模式已跳过本地检查，这部分是对的。
- 远程模式下，`src/main/index.ts:726` `start-gateway` 和 `restartGateway` 的几个调用点（`:424`、`:498`、`:761`）是否要加远程守卫：只有 `:612` 有。
- `src/main/office-start.ts:34` 已限定 `conn.mode === "local"`。
- 另有一个启动路径：`ensureInitialized()` 和 `startHealthPolling` 也调用 `getApiUrl()`。

**【4 现有测试与约定】**
- `tests/connection-config-security.test.ts:79-104`：起一个对所有路径都回应的 http server，断言 `testRemoteConnection(url)` 为 true，错 key 为 false。它不区分路径，所以改成探测 `/v1/health` 或 `/v1/models` 不会破坏它。
- 同文件 `:37-77` 断言 `resolveConnectionApiKeyUpdate` 对相同 URL 返回旧 key、对不同 URL 返回 `""`。
- `tests/hermes-api.test.ts:70-75`：mock 远程配置为 `http://test-api.example.com`；`:131`、`:152`、`:173` 用 `r.url.includes("/v1/chat/completions")` 找请求。若规范化后路径变成 `/v1/chat/completions`，断言仍成立。
- 外部规范：OpenAI 兼容约定是 base URL 带 `/v1`、路径为 `/chat/completions`；而 Hermes server 同时暴露 `/health` 和 `/v1/health`。仓库内没有明文约定哪种 URL 才是"标准"。
- 与题面不冲突，但没有现成测试覆盖 `/v1` 后缀、`/models` 或 `/api/health`。隐藏测试大概率新增在 `tests/connection-config-security.test.ts` 或 `tests/hermes-api.test.ts` 的风格上，针对 URL 规范化或 `testRemoteConnection` 的探测路径。

**【5 边界与隐含要求】**
- URL 以 `/v1`、`/v1/` 结尾，或 `/v1` 前还有路径前缀（反向代理，如 `https://host/hermes/v1`）。只剥离末尾的 `/v1`，不要误删中间的 `v1`。
- 末尾多个 `/`。
- 大小写：`/V1`。
- 校验探测的路径选择：`/health` 失败时是否回退到 `/v1/health`、`/v1/models`；某些服务器只有 `/v1/models` 受鉴权保护，`/health` 可能不验 key，所以只测 `/health` 并不能确认 key 正确。
- `resolveRemoteApiKey` 与 `getApiUrl` 的规范化要一致，`…:8642` 与 `…:8642/v1` 应视为同一个服务器。
- 远程模式下不应触发本地 spawn；这包括 `start-gateway` 和 `restartGateway` 路径。
- stale 本地状态：题面第 4 问要求忽略或重置，但没有具体要求。
- 非 200 响应（401、404）的错误信息；题面的 `ECONNREFUSED` 属于真实网络问题，不是代码缺陷。
- `/api/jobs` 在服务端没有时不应抛错；现在已 `return []`，但会在控制台打 404。

**【6 改动规模】**
- 最小修复：`hermes.ts` 里 1 到 2 处（`getApiUrl` 增加 `/v1` 规范化，`testRemoteConnection`/`resolveRemoteApiKey` 共用）。
- 完整修复还要：`index.ts` 里 `start-gateway`、`restartGateway` 的远程守卫（约 2 到 4 处），以及可选的 i18n 文案（多个 locale）。
- 都是局部修补，不需要新增结构，也不贯穿多层。预计改 2 到 3 个源文件，另加测试。

**【7 难点一句话】**
难点在判断范围：根因其实很窄（`/v1` 后缀导致 `/v1/v1/...`），题面却把 404、ECONNREFUSED、本地 spawn 混在一起，隐藏测试具体覆盖哪几项并不明确。需要决定规范化放在哪一层，以及校验该探测哪个路径。