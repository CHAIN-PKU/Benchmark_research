## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名、但很可能也要一起处理的位置
- `modules/caddyhttp/reverseproxy/selectionpolicies.go` 里 `CookieHashSelection.Select` 内的 `selectNewHost` 是唯一的 `http.SetCookie` 调用点（约第 658 行），目前写的是 `Secure: false`。Secure 和 SameSite 两个属性都要在这里处理，不要只改一个。
- 浏览器要求 `SameSite=None` 必须同时带 `Secure`，否则会被拒收。所以这两个属性是成对的，要一起设置。
- 先用 grep 确认仓库里没有其他设置 sticky cookie 的地方。我查到的结果是 `reverseproxy` 目录下只有这一处。

B. 题面没给例子、但很可能被检查的输入/边界情况
- 请求是明文 HTTP，没有 TLS（`req.TLS == nil`）。题面只给了 HTTPS 的例子。`SameSite=None` 加 `Secure` 在明文请求上，浏览器会拒收这个 cookie。你需要决定明文请求下怎么处理，并去 `reverseproxy.go`、`caddyhttp` 里看看有没有判断请求是否为 TLS 的现成写法或约定。
- 请求经过上游代理、`X-Forwarded-Proto` 为 https 的情况，看仓库里怎么判定「是否安全连接」。
- cookie 已存在且匹配时，不会重新写入。cookie 存在但没有匹配的上游时，会走 `selectNewHost` 重新下发，这条路径也要带上新属性。

C. 仓库里已有的约定、文档或测试
- `selectionpolicies_test.go` 的 `TestCookieHashPolicy`（约第 634 行）和 `TestCookieHashPolicyWithFirstFallback`（约第 690 行）用 `httptest.NewRecorder` 和一个默认的 `http.NewRequest`。这类请求没有 TLS，所以测试里读到的 cookie 属性会取决于你对明文请求的处理方式。
- 修改后要核对这两个测试是否仍然通过。
- `UnmarshalCaddyfile` 的文档注释（约第 687 行）描述了 `lb_policy cookie` 的语法和默认值。如果行为变了，可以考虑在这里或 `CookieHashSelection` 结构体的字段注释里说明默认值。
- 再检查一下 `caddyconfig/caddyfile` 的适配测试和 `caddytest/integration` 里有没有断言 Set-Cookie 内容的用例。

D. 建议提交前额外自测的情况
1. 用带 TLS 的请求（`req.TLS` 非空）调用 `Select`，检查响应 cookie 的 `Secure` 和 `SameSite` 是否都正确。
2. 用普通 HTTP 请求调用 `Select`，检查 cookie 的属性是否符合你选定的行为，并确认没有产生浏览器会拒收的组合。
3. 发一个带过期或不匹配 cookie 的请求，确认重新下发的 cookie 也带新属性。同时运行原有的两个 cookie 测试。
