我已经查完了，下面是档案。

# 仓库档案：API-key 欠费无提示（nanobot）

## 【1 题面要点】
- 原话：“There is no response for chat when api-key in arrearage, please give me a warning”。要求用户在 API key 欠费时能看到明确警告。
- 没有复现步骤、期望输出文本，也没有修法建议。
- 题面末尾的 “Evaluation contract” 才是真正的规格：
  - 判为欠费的情形：HTTP 402；规范化的 billing/quota token（`insufficient_quota`、`quota_exceeded`、`quota_exhausted`、`billing_hard_limit_reached`、`payment_required`）；明确的账单文本（“exceeded your current quota”、“insufficient balance”、“payment required”）。
  - 输出要求：非空的账单专用提示，不暴露原始 provider dump，并且优先于配置的通用 error_message。
  - 不算欠费：纯 429 `rate_limit_exceeded`、超时、连接失败、5xx、成功响应、只是提到 quota 的普通文本。
  - 持久化要求：session 历史里只存现有的 model-error 占位符。
- 接口：`LLMProvider.is_arrearage_response(cls, response: LLMResponse) -> bool`，放在 `nanobot/providers/base.py`，是 classmethod。

## 【2 相关代码】
- `nanobot/providers/base.py:49-65`：`LLMResponse`，含 `error_status_code`、`error_type`、`error_code`、`error_kind`、`error_should_retry`。
- `base.py:119-165`：已有 `_NON_RETRYABLE_429_ERROR_TOKENS`（含 insufficient_quota、quota_exceeded、payment_required 等）和 `_NON_RETRYABLE_429_TEXT_MARKERS`（含 “exceeded your current quota”、“insufficient balance”、“payment required”）。这些可以复用，但目前只用于 429。
- `base.py:319-350`：`_normalize_error_token`、`_extract_error_type_code`。`base.py:352-371`：`_is_retryable_429_response`。
- `base.py:300-316`：`_is_transient_response`。`base.py:722-816`：`_run_with_retry`，非瞬时错误直接返回。
- `nanobot/providers/openai_compat_provider.py:1268-1299`：`_handle_error`。把 body 截 500 字符拼成 `"Error: {body}"` 作为 `content`，也就是原始 dump，并带上 `_extract_error_metadata`（status/type/code）。
- `nanobot/agent/runner.py:506-510`：关键点。`final_content = clean or spec.error_message or _DEFAULT_ERROR_MESSAGE`。`clean` 来自 `response.content`（runner.py:426），所以现在用户看到的是原始 dump，或者在 content 为空时看到通用错误。需要在这里加入欠费分支，优先于 `clean` 和 `spec.error_message`。
- `runner.py:55-56`：`_DEFAULT_ERROR_MESSAGE` 和 `_PERSISTED_MODEL_ERROR_PLACEHOLDER`。`runner.py:1097-1100`：`_append_model_error_placeholder`，现有逻辑已只存占位符。
- `nanobot/agent/loop.py:782`：传 `error_message="Sorry, I encountered an error calling the AI model."`。loop.py:816-817 在 `stop_reason == "error"` 时记录日志。
- `nanobot/agent/subagent.py:251`：`error_message=None`。

## 【3 并列与牵连】
- 其他 provider 也构造错误响应，需要确认能带上 402 状态码和 type/code：`anthropic_provider.py:77-108`、`bedrock_provider.py:645-674`、`openai_codex_provider.py:178+`、openai_compat。分类逻辑放在 base 的 classmethod 里就能统一。
- `fallback_provider.py:249-273` 的 `_should_fallback`：402 不在 `{400,401,403,404,422}` 里，文本里有 `insufficient_quota` 就会 fallback。不改也许可以，但要核实 402 的行为是否合理。
- `_run_with_retry` / `_is_transient_response`：402 已落入“非瞬时”分支（base.py:316 的文本标记里没有 402）。注意：非瞬时错误且带图片时会先去掉图片重试一次（base.py:761-773），欠费时这次重试是多余的。
- `nanobot/agent/memory.py:660` 也处理 `finish_reason == "error"`，是否要提示需要确认。
- 现有 429 分支（`_is_retryable_429_response`）和新方法共用同一批 token/文本，建议抽公共 helper，避免两份列表漂移。
- subagent（`error_message=None`）走同一个 runner，也会受影响。

## 【4 现有测试与约定】
- `tests/agent/test_runner_errors.py:58-78`：`content="429 rate limit exceeded"` 时断言 `result.final_content == "429 rate limit exceeded"`，并且 session 消息里没有 "429"，末条是 `_PERSISTED_MODEL_ERROR_PLACEHOLDER`。这条要保持通过，说明纯 429 仍要透传 `content`，只有欠费才改写。
- `tests/providers/test_provider_retry.py:396-415`：429 + `insufficient_quota` 时 `calls == 1`、无 sleep，仍应不重试。
- `tests/providers/test_openai_codex_provider.py:348, 392`：insufficient_quota 的 `should_retry` 为 False。
- `tests/agent/test_loop_runner_integration.py:224-265`：占位符的持久化行为。
- 仓库没有外部规范。约定是：错误内容不进历史，只存占位符。与题面不冲突。
- 隐藏测试大概率包括：
  - `is_arrearage_response` 的真假表；
  - runner 的 `final_content` 为账单提示，且不含原始 dump；
  - 优先于 `spec.error_message`；
  - 历史里只有占位符。
- 具体的提示文案没有指定，测试可能只断言非空、不含原文、含 billing 之类的关键词。

## 【5 边界与隐含要求】
- 402 且 content 为空时也要判为欠费。
- token 要做大小写和规范化（`_normalize_error_token`）。
- 文本标记应放宽到任意状态码，但不能因为普通文本提到 “quota”（如 “quota” 一词单独出现）就误判。要求的是“明确的账单文本”，所以不能用过宽的子串。
- 429 + `rate_limit_exceeded` 必须为 False。429 + `insufficient_quota` 为 True。
- 超时、连接失败、5xx、成功响应（`finish_reason != "error"`）为 False。
- 提示不能回显 `response.content` 的原始 JSON。
- 优先于 `spec.error_message`，而该字段默认非空，所以不能写成 `clean or ...` 的顺序。
- 流式路径：错误响应走 `chat_stream_with_retry`，需确认 runner 里流式和非流式汇合到同一个 error 分支（runner.py:506）。
- 需要确认 `on_retry_wait` 等进度提示不会漏出原始 dump。

## 【6 改动规模】
- 主改动 2 个文件：`base.py` 新增分类方法和 helper，`runner.py` 的 error 分支加提示。
- 可能附带改动：`fallback_provider.py`、`openai_compat_provider.py`（保证 402 元数据）。
- 局部修补，不需要新结构。一般 3–6 处。

## 【7 难点一句话】
分类本身可以复用现有 token/文本表，容易；难点在于判定边界要精确（402 与账单文本为真，429 速率限制与“只是提到 quota”为假），以及要让欠费提示在 `runner.py:507` 压过 `clean` 和 `spec.error_message`，同时保证现有 429 透传测试仍通过。