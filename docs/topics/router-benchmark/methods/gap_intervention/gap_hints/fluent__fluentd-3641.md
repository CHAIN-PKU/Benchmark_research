## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名但很可能要一起处理的位置
1. 根因在 lib/fluent/rpc.rb 的 Server#initialize：用 endpoint.split(':') 拆 bind/port，对 `[::]:24444` 会拆错。题面报错栈在 in_forward/TLS 路径，容易误导，应以 rpc.rb 为准。
2. @bind/@port 还被 start 里的 debug 日志 `listening RPC http server on http://#{@bind}:#{@port}/` 使用；IPv6 地址放进 URL 要带方括号，改完核对日志输出。
3. lib/fluent/supervisor.rb 的 run_rpc_server 和 config[:rpc_endpoint] 只是透传字符串，一般不用改；但要确认 `[::]` 在 system_config.rb 的 `config_param :rpc_endpoint, :string` 解析阶段不会被当成数组或其他语法处理。
4. WEBrick 的 BindAddress 对 IPv6 期望的格式（带不带方括号）需要查证，可看 webrick 自身代码或在本地用 ruby 试。

B. 题面没给例子但可能被检查的输入
1. 带方括号的 IPv6：`[::]:24444`、`[::1]:24444`、`[2001:db8::1]:24444`。
2. 原有 IPv4 写法不能回归：`0.0.0.0:24444`、`127.0.0.1:24445`。
3. 主机名形式 `localhost:24444`。
4. Port 的类型：现在传给 WEBrick 的是字符串，检查拆分后端口类型是否仍被接受。

C. 仓库里已有的约定、文档或测试
1. test/test_supervisor.rb 的 44、72、225、262 行附近已有 rpc_endpoint 用例（IPv4 的 127.0.0.1、0.0.0.0），改动后必须仍通过。
2. 其他 bind 类配置（plugin_helper/server.rb、in_forward 一带）对 IPv6 的处理方式可作参考。
3. 仓库里没有专门针对 Fluent::RPC::Server 的测试（如 test_rpc.rb），先检查 test/ 下是否已有，再决定是否补一个。

D. 提交前建议自测
1. 直接构造 Fluent::RPC::Server.new('[::]:24444', log)，检查 @bind 和 @port 是否分别为 IPv6 地址和端口；环境支持 IPv6 时实际 start 并用 curl 访问 /api/config.dump。
2. 分别用 `[::1]:24444` 和 `127.0.0.1:24444` 构造，确认两者都能成功监听。
3. 检查 start 的 debug 日志输出，以及 shutdown 能否正常停止。
