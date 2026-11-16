**档案：fluentd in_http 增加 add_tag_prefix**

**【1 题面要点】**
- 要求：`in_http` 的 `<source>` 增加 `add_tag_prefix` 参数，给 HTTP 路径生成的 tag 统一加前缀。
- 动机：路径 `/xxx` 目前直接成为 tag，调用方可以随意指定，可能与其他 tag 冲突。
- 题面原文："I would like to solve this by specifing some tag prefix in source section of fluentds in_http plugin"，另有 "add_tag_prefix already works great in in_forward plugin."
- 没有复现步骤，没有期望输出示例，也没有给修法。只提示了可参照 in_forward。
- 没写 tag 与前缀之间的分隔符，也没写空值的处理。

**【2 相关代码】**
- `lib/fluent/plugin/in_http.rb:61-86`：`config_param` 声明区。`add_query_params` 在 86 行，新参数大概加在这里。
- `in_http.rb:112-146`：`configure`。现在没有任何参数校验，可在此加空串检查。
- `in_http.rb:202-251`：`on_request(path_info, params)`。
  - 204-205 行：`path = path_info[1..-1]; tag = path.split('/').join('.')`。
  - 234 行：`router.emit_stream(tag, mes)`。
  - 前缀逻辑最自然的位置是 205 行之后、234 行之前。
- 解析请求体时的 `parse_params*` 以及 Handler（约 340 行以后）与 tag 无关。

**【3 并列与牵连】**
- 参考实现 `lib/fluent/plugin/in_forward.rb`：
  - 68 行：`config_param :add_tag_prefix, :string, default: nil`。
  - 115 行：`raise Fluent::ConfigError, "'add_tag_prefix' parameter must not be empty" if @add_tag_prefix && @add_tag_prefix.empty?`。
  - 305 行：`tag = "#{@add_tag_prefix}.#{tag}" if @add_tag_prefix`。
- in_http 里 tag 只在 `on_request` 一处生成并 emit，没有并列的 tag 生成点。没发现第二个入口，比如批量或其他路径。
- `lib/fluent/compat/handle_tag_name_mixin.rb` 是旧的 mixin，与此无关，不需要改。
- 不改参数的默认值，所以不影响现有部署。
- 仓库里没找到 in_http 的文档或 README 参数表，文档在仓库外。CHANGELOG 由发布流程维护，大概不用改。

**【4 现有测试与约定】**
- `test/plugin/test_in_http.rb:44-52` 的 `test_configure` 断言默认值，如 `assert_equal false, d.instance.add_query_params`。新参数可能在这里新增默认值断言，比如 `nil`。
- in_http 现有测试都用 `post("/#{tag}", ...)`，再用 `d.events` 比对 tag。例如 `test_time` 里是 `["tag1", time, {"a" => 1}]`。
- in_forward 的测试 `test/plugin/test_in_forward.rb:277-286`，用 `data(...)` 加 `test 'tag parameters'`。里面 `add_tag_prefix: { param: "add_tag_prefix new_prefix", result: "new_prefix.tag1" }`，说明约定是 `前缀.tag`，用点连接。
- 与题面不冲突，题面没有给出相反的期望。

**【5 边界与隐含要求】**
- 分隔符：用 `.`，与 in_forward 一致。前缀本身不应自带结尾的点。
- 空串前缀：in_forward 在 configure 时抛 `ConfigError`，隐藏测试可能会测这一点。
- 默认 nil 时行为必须不变。
- 路径为 `/` 时 tag 是空串，加前缀后会变成 `prefix.`。这种情况题面没提，可能不处理。
- 路径中的 `/` 先转成 `.`，再加前缀，保证 `/a/b` 得到 `prefix.a.b`。
- 前缀要对所有请求格式生效，包括 json、msgpack、自定义 parser 和 multi 事件。因为 tag 只算一次，所以自动满足。
- 多 worker 和 `compat_parameters` 不受影响。

**【6 改动规模】**
- 只改 1 个源文件 `in_http.rb`，3 处：一个 `config_param`（带 `desc`）、一条 configure 校验、一行 tag 拼接。
- 测试要新增 1-2 个用例，在 `test_in_http.rb`。
- 局部小补丁，不需要新结构，也不跨层。

**【7 难点一句话】**
- 实现本身很小，直接照抄 in_forward。主要风险是隐藏测试可能覆盖的细节：空串报错的消息文字、`.` 分隔符，以及这个参数是否同时有 `add_tag_suffix` 之类的扩展。