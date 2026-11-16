# 仓库档案：`default_bind` 支持多个地址

## 【1 题面要点】
- 期望行为：全局选项 `default_bind` 像 `bind` 指令一样接受多个地址，例如 `default_bind [2001:db8:11:ad::80] 198.51.100.184`。没有 `bind` 的站点应监听所有这些地址。
- 现状有两种：
  - 写两个地址时，解析报错：`Wrong argument count or unexpected line ending after '198.51.100.184'`。
  - 分两行各写一个 `default_bind` 时，只有最后一个生效。
- 题面给了复现和错误输出。没有期望的 JSON 输出，也没有修法建议。唯一的期望是 "support multiple IP addresses"，参照对象是 `bind`。
- 站点自己写了 `bind` 时，应覆盖 `default_bind`。这是 `bind` 已有的行为，题面示例用到了它。

## 【2 相关代码】
- `caddyconfig/httpcaddyfile/options.go:32`：`RegisterGlobalOption("default_bind", parseOptSingleString)`。
  - `parseOptSingleString`（270-280）读一个参数，之后如果还有 token 就返回 `ArgErr`。这就是报错的来源。
  - 返回值类型是 `string`。
- `caddyconfig/httpcaddyfile/addresses.go:216-217`，位于 `listenerAddrsForServerBlockKey`（177-241）：
  ```go
  if defaultBind, ok := options["default_bind"].(string); ok {
      lnHosts = []string{defaultBind}
  ```
  它用类型断言 `.(string)` 取值，并且只放一个主机。
- `addresses.go:223-232` 对 `lnHosts` 逐个拼 `host:port`，用 map 去重。unix 网络地址不拼端口。
- `builtins.go:57-63` 的 `parseBind` 用 `RemainingArgs()` 收集多个地址，是参考实现。

## 【3 并列与牵连】
- 全仓库只有这两处读写 `default_bind`（addresses.go 和 options.go）。我没有找到其他调用点。
- `options.go:34` 的 `default_sni` 也用 `parseOptSingleString`，不能改动这个共用函数，否则会影响 `default_sni`、`acme_ca`、`email`、`key_type` 等选项。需要新增一个解析函数，或把返回类型换成 `[]string`。
- 返回类型一旦改成 `[]string`，`addresses.go:216` 的 `.(string)` 断言必须同步修改，否则静默失效，默认绑定被忽略。编译器不会报错。
- `tlsapp.go:150` 处理 `bind` 的 ACME `BindHost`，只读 `sblock.pile["bind"]`，不读 `default_bind`。
  - 目前 `default_bind` 本来就不影响 ACME 的 BindHost，所以这是现状，不是新引入的问题。
  - 这里有 "only binding to one host is supported" 的注释，我没有读完这段。
- `addresses.go:100-103` 的 `addrToKeys` 和后面的 `consolidateAddrMappings` 已经能处理多个监听地址，因为 `bind` 多地址早已支持。
- 第 236 行的输出列表来自 map 遍历，顺序不确定。我没有查后续是否排序，这对隐藏测试的 JSON 顺序有影响（见第 5 点）。

## 【4 现有测试与约定】
- `caddytest/integration/caddyfile_adapt/global_options_default_bind.txt:2`：`default_bind tcp4/0.0.0.0`，期望 `"listen": ["tcp4/0.0.0.0:12345"]` 和 `["tcp4/0.0.0.0:443"]`。单值行为必须保持不变。
- `bind_ipv6.txt:2`：`bind tcp6/[::]`，是 `bind` 的适配器测试。
- 这些是 adapt 测试，用 `----------` 分隔输入和 JSON。隐藏测试很可能是新增或修改这类 `.txt` 文件，加一个多地址的 `default_bind`。
- 没有找到 `default_bind` 的 Go 单元测试。
- 约定：`bind` 的多参数语义是参考。没有与题面冲突的规范。

## 【5 边界与隐含要求】
- 站点自己写了 `bind` 时，`default_bind` 不应被合并进去，而是整体被替换。当前 `len(lnHosts)==0` 的分支已经是这个语义，要保留。
- 多次出现 `default_bind`（题面第二种写法）：
  - 应该累加，还是保持单次语义？题面把它列为"只有最后一个生效"的现象，但没有明确要求累加。
  - 如果实现用 `for d.Next()` 加 `RemainingArgs()` 累加，两种写法都会工作。
- 去重：同一地址重复出现时，由 map 去重。
- 带 `tcp4/` 之类前缀的地址和 unix socket 地址要继续走原有的拼端口逻辑。
- 空的 `default_bind`（没有参数）应继续报 `ArgErr`。
- 输出顺序：
  - 监听列表来自 map 遍历，随机顺序。
  - 如果隐藏测试的预期 JSON 里多个地址有固定顺序，实现可能需要排序。
  - 如果在这里新增排序，`bind` 多地址的现有测试可能也受影响。
  - 此处是推测，我没有验证后续代码是否已有排序。
- IPv6 方括号写法（`[2001:db8::80]`）拼端口后得到 `[2001:db8::80]:443`，这个能用。

## 【6 改动规模】
- 约 2 个文件、3-4 处：
  - 新增或修改 `options.go` 的解析函数，并改 `RegisterGlobalOption` 的注册。
  - 修改 `addresses.go:216-217` 的类型断言和赋值。
  - 加一个测试文件，可选。
- 局部修补，不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
改动本身很小，主要风险是漏改读取处的 `.(string)` 断言（编译通过但行为静默失效），以及多地址输出的顺序是否与隐藏测试的预期一致。