# 档案：in_http 支持 `application/x-ndjson`

仓库里没有 git 历史，以下均来自代码阅读。

## 【1 题面要点】
- 要求的行为：`in_http` 接收 `Content-Type: application/x-ndjson` 的请求。请求体是按换行分隔的多个 JSON 对象，应被当作多条事件处理。
- 复现、期望输出、修法建议：题面都没有给。
- 关键句：
  - "Implement support for Content-Type application/x-ndjson for newline-delimited JSON objects to be summited via the in_http input plugin."
  - "out_http plugin supports application/x-ndjson … complementary"
- 题面没说 ndjson 的每一行如何产生事件、时间怎么取、坏行怎么处理。
- 这些细节要靠现有 in_http 的批量 JSON 行为推断，隐藏测试很可能照 `test_application_json` 的写法来断言。

## 【2 相关代码】（均在 `lib/fluent/plugin/in_http.rb`）
- `Handler#on_message_complete`（516–607）：
  - 559–570 按 Content-Type 分支，决定把请求体放进 `params`。
  - `@format_name != 'default'` 时（自定义 `<parse>`）：所有请求体进 `params['event_record']`，不看 Content-Type。
  - 否则：form-urlencoded、multipart、`^application/json` 设 `params['json']=@body`（566–567）、`^application/msgpack` 设 `params['msgpack']`（568–569）。
  - 新增的 ndjson 分支最自然的位置是 566 附近。
- `parse_params_default`（308–320）：
  - 取 `params['msgpack']` 或 `params['json']`。
  - 用 `@parser_json.parse(js)` 解析，返回 `[nil, record]`。
  - 都没有则 `raise "'json' or 'msgpack' parameter is required"`。
- `on_request`（202–285）：
  - 调 `parse_params`，`record` 为 `Array` 时走 `MultiEventStream`，逐条处理 `add_params_to_record`、`params['time']`、`convert_time_field`。
  - 非 Array 则 `router.emit`。
  - 外层 `rescue` 返回 400。
- `configure`（123–145）：创建 `@parser_json`，其 `time_key=nil`、`estimate_current_event=false`。
- `lib/fluent/plugin/parser_json.rb:72`：`JSONParser#parse(text)` 一次只解析一个 JSON 文档，解析失败时 `yield nil, nil`。
  - 默认 Oj 的 `Oj.load` 对多文档字符串不一定按预期处理。
  - 因此需要自己按 `\n` 切分后逐行解析，或把各行拼成数组。

## 【3 并列与牵连】
- 并列实现：
  - 默认路径（`parse_params_default`）与自定义 parser 路径（`parse_params_with_parser`）。
  - 自定义 parser 路径下 Content-Type 被忽略，ndjson 请求体会被整体交给 `<parse>`。这可能不需要改，但要确认。
- 成对处理：
  - JSON 与 msgpack 在 `parse_params_default` 里是并列分支，ndjson 是第三种。
  - 可在 `on_message_complete` 里设新 key（如 `params['ndjson']`），也可在此处直接转成数组。
- 复用点：
  - 批量路径（`on_request` 224–240）已经能处理 Array，包括时间、`add_http_headers`、`add_query_params`、`add_remote_addr`。
  - 若 ndjson 解析为 record 数组，几乎无需改 `on_request`。
- 其他：
  - `Content-Encoding` 的 gzip/deflate 解码（542–552）先于分支执行，ndjson 自动受益。
  - `out_http.rb:156` 在 `json_array` 为 false 时用 `application/x-ndjson`，这是对端发送方，不需要改。
  - 文档和 CHANGELOG 可能需要补充，但不影响测试。

## 【4 现有测试与约定】
- `test/plugin/test_in_http.rb`：
  - 499–519 `test_application_json`：`post("/#{tag}?time=...", record.to_json, {"Content-Type"=>"application/json; charset=utf-8"})`，然后 `assert_equal events, d.events`。
  - 521–540 `test_application_msgpack`：写法相同，只换 Content-Type。
  - 153–173 `test_multi_json`：`d.run(expect_records: 2)`，`assert_equal events, d.events`，并断言 `assert_equal_event_time`。
  - 175、227 附近：批量 JSON 的 time 字段处理，包括 time 字段缺失。
  - 411–465：批量时的 `add_http_headers`、`add_remote_addr` 测试。
  - 1014–1035 `test_if_content_type_is_initialized_properly`：检查 Handler 的 `content_type`。
- 约定：
  - 仓库里 ndjson 的参考只有 out_http（`test_out_http.rb:79、166、232` 等），它输出每行一个 JSON。
  - in_http 内没有 ndjson 参考实现。
  - 外部规范是 NDJSON（换行分隔，通常以 `\n` 结尾）。
- 冲突：与现有测试没有冲突，是纯新增。
- 隐藏测试很可能是 `test_application_ndjson` 一类：
  - POST 多行 JSON，Content-Type 为 `application/x-ndjson`。
  - 断言各条事件按行生成。
  - 时间可能来自 `?time=`，也可能来自记录的 time 字段。

## 【5 边界与隐含要求】
- 请求体末尾有 `\n`，中间有空行，或使用 `\r\n`：空行要跳过，不能产生 nil 记录。
- Content-Type 带参数，如 `application/x-ndjson; charset=utf-8`：沿用 `=~ /^application\/x-ndjson/` 的前缀匹配即可。
- 某一行不是合法 JSON：
  - `@parser_json.parse` 对坏行会 `yield nil, nil`。
  - 需决定整体返回 400，还是跳过该行。
  - 现有单 JSON 的行为是 `record.nil?` 时静默返回 200，并写 debug 日志。
- 单行情形：只有一行时，应当产出单条事件还是只有一个元素的数组，两者效果都是一条事件，但路径不同。
  - 单条走 `router.emit`。
  - 数组走 `MultiEventStream`。
- 时间处理：
  - 每行各自按 `convert_time_field` 处理（批量路径已具备）。
  - `?time=` 参数应对所有行生效（批量路径已具备）。
  - `@parser_json.time_key=nil` 意味着时间转换在 `on_request` 里做。
- 若某行解析出非 Hash（如数字或数组），后续 `add_params_to_record` 的 `record[k]=` 会抛异常，并被外层 rescue 成 400。
- 请求体编码：`@body` 初始为 `''`，可能是 ASCII-8BIT，按行切分后用 Oj 解析时的编码行为需留意。
- 自定义 `<parse>` 配置下是否支持 ndjson：题面没提，大概率不要求。

## 【6 改动规模】
- 生产代码：1 个文件（`in_http.rb`），约 1–3 处：Content-Type 分支，加上 `parse_params_default` 里新增的按行解析，或在 Handler 里直接转数组。
- 测试：1 个文件新增用例。
- 局部修补，不需要新增结构或贯穿多层，因为批量 Array 路径已现成可用。

## 【7 难点一句话】
功能本身是小改动。难点在于：
- 题面没规定 ndjson 的语义（空行、坏行、单行、时间），需要对齐批量 JSON 路径的既有行为。
- 隐藏测试可能对这些边界有具体断言，而题面没有给出。