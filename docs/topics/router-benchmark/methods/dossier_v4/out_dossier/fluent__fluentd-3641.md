# 档案：fluentd IPv6 `rpc_endpoint`（`[::]:24444`）

约 14 次搜索/阅读，范围：lib 下的 rpc_endpoint、RPC::Server、peeraddr，test 下的 rpc 用例，以及 supervisor 的调用链。

## 【1 题面要点】
- **要求的行为**：`<system>` 里写 `rpc_endpoint [::]:24444` 时，fluentd 应能在 IPv6 环境正常运行，RPC 服务应能监听 IPv6 地址。
- **复现**：给了配置 `rpc_endpoint [::]:24444` 加 `workers 4`。
- **期望输出**：只有一句 "Fluentd should run fine in IPv6 environment."。
- **修法建议**：没有。
- **报错日志**：是 `Errno::ENOTCONN ... getpeername(2)`，栈在 `plugin_helper/server.rb` 的 `try_tls_accept`、`openssl ssl.rb peeraddr`。这与 RPC 无关，更像用户另一个 TLS 输入或 forward 的问题，属于误导线索。真正原因要从代码里查。
- 题面没给启动失败的直接报错。

## 【2 相关代码】
- **`lib/fluent/rpc.rb:22-34`（`RPC::Server#initialize`）**是最可能的根因。
  - 第 23 行 `bind, port = endpoint.split(':')`，对 `[::]:24444` 会拆成多段。
  - `bind` 变成 `"["`，`port` 变成 `""`，随后传给 `WEBrick::HTTPServer.new(BindAddress:, Port:)`，必然出错或绑定错误。
  - 第 76 行 `start` 的日志 `http://#{@bind}:#{@port}/` 对 IPv6 需要带方括号才是合法 URL。
- **`lib/fluent/supervisor.rb:84-85`（`run_rpc_server`）**用 `RPC::Server.new(@rpc_endpoint, $log)` 创建服务。
  - `supervisor.rb:52-55` 的 `before_run` 在有 `config[:rpc_endpoint]` 时调用它。
  - `supervisor.rb:444` 把 `params['rpc_endpoint']` 传入，`supervisor.rb:817` 从 `@system_config.rpc_endpoint` 取值。
- **`lib/fluent/system_config.rb:44`**：`config_param :rpc_endpoint, :string`，只是字符串，不做校验。
- **`plugin_helper/server.rb:693-720`（`try_tls_accept`）**是日志里出现的栈，与 RPC 无关，大概率不用改。

## 【3 并列与牵连】
- 这个 `endpoint.split(':')` 的解析只有 `rpc.rb:23` 一处。
- 同样的 `host:port` 解析可能还存在于：
  - `counter_server`，即 counter 的 `bind`/`port`。我没有细查，看起来是分开的参数。
  - `in_monitor_agent`、`in_http` 这类插件，它们用 `bind` 和 `port` 两个独立参数，不受影响。
- 唯一调用点是 `supervisor.rb:85`。
- 改 `RPC::Server` 会影响所有用 RPC 的路径：
  - `fluent-ctl` 之类的命令。
  - Windows 的 `test_rpc_server_windows`。
  - 对外的 `/api/*` 端点。
- 还要注意 `@bind` 的用法。WEBrick 的 `BindAddress` 需要不带方括号的 `::`，日志 URL 则需要带括号。

## 【4 现有测试与约定】
- `test/test_supervisor.rb:216-251`（`test_rpc_server`）：
  - 配置 `rpc_endpoint 0.0.0.0:24447`，用 `Net::HTTP.get(URI.parse('http://127.0.0.1:24447/api/plugins.flushBuffers'))` 请求。
  - 断言 `assert_equal('{"ok":true}', response)` 和 `$log.out.logs.first.end_with?(info_msg)`。
  - 其中 `pend unless $log.out.logs.first` 说明 macOS 上可能被跳过。
- `test/test_supervisor.rb:253-284`（Windows 版）同样只测 IPv4。
- `test_supervisor.rb:44` 和 `:72` 只测配置解析为字符串 `'127.0.0.1:24445'`。
- 没有任何 IPv6 用例，也没有针对 `RPC::Server` 的单测。
- 仓库里没有地址解析的参考实现或工具函数。
  - 外部规范是 RFC 3986 的 `[v6]:port` 写法。
  - Ruby 的 `URI`、`Addrinfo`、`IPAddr` 可用。
- 与题面期望不冲突。隐藏测试大概率是把 `test_rpc_server` 参数化，加一个 `[::1]:24447` 或 `[::]:24447` 的用例，并用 `http://[::1]:24447/...` 请求。

## 【5 边界与隐含要求】
- IPv4 的 `0.0.0.0:24447` 和 `127.0.0.1:24445` 行为必须不变。
- 要同时支持 `[::]:port` 和 `[::1]:port`。
- 方括号要去掉后再传给 WEBrick，端口建议转成整数，现在是字符串。
- 没有方括号的裸 IPv6（如 `::1:24444`）有歧义，需要决定是拒绝还是尽量解析。
- 没有端口、格式错误时的行为，现状是静默出错。
- 日志里的 URL 在 IPv6 下应写成 `http://[::]:24444/`。
- 测试环境不一定有 IPv6，可能需要 `omit`。
- WEBrick 对 `::` 的绑定在 Linux 上通常是双栈。
- 题面的 TLS 栈与此无关，不要去改 `server.rb`。

## 【6 改动规模】
- 约 1 个源文件（`lib/fluent/rpc.rb`）、1 处解析逻辑，加十来行代码。
- 顺带可能改 `start` 的日志行。
- 测试在 `test/test_supervisor.rb` 里加参数化用例，也可能新增 `test/test_rpc.rb`。
- 属于局部修补，不新增结构、不贯穿多层。

## 【7 难点一句话】
**难点**：题面给的 TLS 报错栈把人引向 `plugin_helper/server.rb`，而真正的根因是 `rpc.rb:23` 里简单的 `split(':')`。找到这一点后，修法就是处理 `[addr]:port` 并去掉方括号，难度偏低。需要留意的只有日志 URL 和与隐藏测试的细节对齐，比如端口是否转整数、`@bind` 是否保留括号。