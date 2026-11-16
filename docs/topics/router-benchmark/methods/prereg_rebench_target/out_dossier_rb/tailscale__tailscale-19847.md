以上查证够了，下面给出档案。

# 仓库档案

## 【1 题面要点】
- 要求的行为：在 Linux + systemd-resolved 下，关闭 MagicDNS、没有全局 DNS（没有 default resolver）、但存在 app connector 时，Tailscale 应当向 OS 注册 split DNS，让连接器相关域名的 DNS 请求走 Tailscale。现在的结果是 OS 完全没有用到 Tailscale 做 DNS。
- 复现：只有一行环境描述（"Linux w/ systemd-resolved / Turn off MagicDNS / No global dns fallback"）。没有日志、没有版本号、没有期望输出。
- 修法建议：没有。"No new interfaces are introduced."
- 题面没有说明路径。**题面没有指明是哪个层出了问题**，需要自己定位。

## 【2 相关代码】
- `ipn/ipnlocal/node_backend.go:852` `dnsConfigForNetmap`，由 `local.go:5616` 经 `nodeBackend.dnsConfigForNetmap`（`node_backend.go:742`）调用。负责把 netmap 和 prefs 转成 `dns.Config`。
  - 1034–1051 行是 conn25 的 split DNS 路由。它调用 `appc.PickSplitDNSPeers`，再用 `peerAPIBase` 构造 `{Addr: "<base>/dns-query"}`，也就是 **DoH 形式的 http URL**，最后交给 `addSplitDNSRoutes`。
  - 1057–1077 行的 fallback switch：`len(dcfg.Routes)==0` 这个 case 是空的。
  - 964 行 `if !prefs.CorpDNS() { return dcfg }` 会提前返回，而且在 conn25 代码之前。
- `net/dns/manager.go:295` `compileConfig`，把 `dns.Config` 编译成 resolver 配置和 `OSConfig`。**我认为这里最可能是出错点**：
  - 370–376 行：`len(cfg.singleResolverSet())>0 && m.os.SupportsSplitDNS() && !isWindows && !isApple` 时，走 `ocfg.Nameservers = toIPsOnly(cfg.singleResolverSet())` 加 `MatchDomains`。
  - `toIPsOnly`（454 行）只保留 port 53 的普通 IP。`dnstype.Resolver.IPPort()`（`types/dnstype/dnstype.go:49`）对以 `h` 或 `t` 开头的地址直接返回 !ok。
  - 因此，如果所有 Routes 都指向同一个 DoH 连接器（例如 `http://100.x:port/dns-query`），Nameservers 会变成**空**，MatchDomains 还在。systemd-resolved 实际上没有收到任何有效配置。
  - 对比 326 行 `hasDefaultIPResolversOnly`（做了 DoH 和端口检查），以及 378–382 行的"指向 quad-100"路径（正确做法）。
- `net/dns/config.go:104-186`：`needsOSResolver`、`singleResolverSet`、`matchDomains`、`hasDefaultIPResolversOnly`。
- `appc/conn25.go:59` `PickSplitDNSPeers`：决定哪些域名对应哪些连接器 peer，并去掉自己负责的域名。

## 【3 并列与牵连】
- `compileConfig` 里有两个并列路径：
  - 单一 resolver set 的 split 路径（370 行）。
  - 默认 resolver 的 trivial 路径（326 行，已经做了 IP 检查）。
  - 前者没有做同样的检查，这是并列缺口。
- 题面写的是 `Linux` 加 `systemd-resolved`。`SupportsSplitDNS` 对 resolved、NetworkManager 等 OS 配置器都成立，所以所有这些后端都受影响。
- 改 `singleResolverSet` 或 370 行的条件，会影响所有使用 split DNS 的场景：
  - 普通 control 下发的 `nm.DNS.Routes`。
  - exit node 的 DoH 路由（`useWithExitNodeRoutes`）。
  - 一般的 split DNS 配置。
- 如果改的是 `dnsConfigForNetmap`，影响 `local_test.go:2816` 和 `dnsconfig_test.go:487` 的多个用例。
- 如果还要补 MagicDNS 关闭时的 hosts 处理，就牵涉 `propagateHostsToOS`、`LocalDomains`。

## 【4 现有测试与约定】
- `ipn/ipnlocal/dnsconfig_test.go:393-481`：
  - `conn25-split-dns` 期望 `Routes: {"example.com.": {{Addr: "http://100.102.0.1:1234/dns-query"}}}`，`AcceptDNS: true`，并且 DefaultResolvers 为空。
  - `conn25-split-dns-no-matching-peers` 期望 `Routes: {}`。
  - 这说明 netmap 到 `dns.Config` 这一层，现有测试已经覆盖并且预期是对的。
- `net/dns/manager_test.go`：
  - 421–452 行 `routes`、`routes-split`，用的都是 `upstreams("corp.com","2.2.2.2")` 这种普通 IP。
  - 809 行有 `nextdns-doh`，但那是默认 resolver 的路径。
  - 我没有找到 "Routes 里只有 DoH 或 http resolver 且 split=true" 的用例。隐藏测试大概率加在这里，用 `split: true`，期望 `Nameservers = serviceAddr46`，`rs.Routes` 带着 DoH 路由。
  - 测试里 `split` 字段控制 `SupportsSplitDNS`。
- 约定：manager.go:378-382 的注释写明，"multiple upstream routes ... Install a split config pointing at quad-100"。DoH 或自定义端口 resolver 本来就应该通过 quad-100 转发，因为 OS 解析器只能配置 IP:53。
- 与题面不冲突，只是题面没有说明。

## 【5 边界与隐含要求】
- "只有一个 set 的 resolver 但是是 DoH" 要退到 quad-100 路径：
  - `rcfg.Routes = routes`
  - `ocfg.Nameservers = serviceIPs`
  - `MatchDomains` 为各路由域名
- 混合：IP 和 DoH 同时出现，或端口不是 53（`toIPsOnly` 会悄悄丢掉）。要对 resolver 整体判断，不要只看第一个。
- Routes 里有空 resolver 的条目（MagicDNS 本地域名）时，`routes` 与 `rcfg.LocalDomains` 的关系。`singleResolverSet` 对空 resolver 的处理要小心，空 set 返回 nil 且 `len==0`，会被当作"没有 single set"。
- 非 split 的 OS（`!SupportsSplitDNS`）和 Apple、Windows 本来就不走 370 行，不能回归。
- `publicdns.IPIsDoHOnlyServer` 也应该一并考虑，`hasDefaultIPResolversOnly` 里有这个检查。
- 另一种可能：问题其实在 netmap 这一层，例如 `AcceptDNS` 或 `CorpDNS` 为 false，或 `PickSplitDNSPeers` 的条件。但现有 `dnsconfig_test.go` 的 conn25 用例显示这一层是对的，所以我认为不是主因。这一点**没有验证到**。
- 我没有读 `manager_linux.go` 和 resolved 的实现，没有核实空 Nameservers 到底怎么被处理。

## 【6 改动规模】
- 预期 1–2 个文件（`net/dns/manager.go`，可能加 `net/dns/config.go` 的 helper），改 1–2 处。
- 局部修补，不需要新结构。
- 测试加在 `net/dns/manager_test.go`。

## 【7 难点一句话】
难点在定位：题面完全没有说明，表面上像 app connector 或 netmap 的问题，而且 `ipnlocal` 层的测试都是对的，真正的缺陷在 `net/dns/manager.go` 的 single-resolver split 路径把 DoH 地址丢成了空 Nameservers；找到之后改法本身很小，但要判断清楚退到 quad-100 的条件边界。

（这是依据代码阅读的推断，没有运行任何测试复现。）