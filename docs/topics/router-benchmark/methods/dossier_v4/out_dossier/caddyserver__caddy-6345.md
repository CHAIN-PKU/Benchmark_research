【1 题面要点】
- 要求：把 JSON 配置里的 `sign_with_root` 开放到 Caddyfile。题面只有一句话，附了 JSON 文档链接和 #6290 评论链接。
- 题面没有复现步骤、期望输出或修法建议。
- 题面没有说是哪个模块。
- 仓库里 `tls { issuer internal { sign_with_root } }` 已经支持，见 `modules/caddytls/internalissuer.go:176`，测试在 `tls_internal_options.caddyfiletest:6`。
- 所以缺的是 `acme_server` 指令。它的 JSON 字段 `Handler.SignWithRoot` 在 `modules/caddypki/acmeserver/acmeserver.go:81`，Caddyfile 解析不认识它，会报 "unrecognized ACME server directive"。
- 题面给的链接是 `.../apps/tls/automation/policies/issuers/internal/`。这个链接指向的是已经支持的那个模块。这一点容易让人误判，需要自己推断真正要改的是 `acme_server`。

【2 相关代码】
- `modules/caddypki/acmeserver/caddyfile.go:46-154` 的 `parseACMEServer` 是主要改动点。
  - switch 分支在 63-141 行，目前有 ca、lifetime、resolvers、challenges、allow_wildcard_names、allow、deny。
  - 需要新增 `case "sign_with_root"`，设置 `acmeServer.SignWithRoot = true`。
  - 29-45 行的注释文档块也要补上这一项。
- `acmeserver.go:81` 是字段定义。
- `acmeserver.go:164-165` 的 `Provision` 把 `SignWithRoot` 传给 `AuthorityConfig`。
- `caddypki/ca.go:197-215` 的 `NewAuthority` 在 `SignWithRoot` 为真时用根证书签发。后端已经完整，不需要改。

【3 并列与牵连】
- 并列实现是 `internalissuer.go:157-184` 的 `UnmarshalCaddyfile`。它的 `sign_with_root` 写法可以直接参照：先 `if d.NextArg() { return d.ArgErr() }`，再 `iss.SignWithRoot = true`。
- 没有其他调用点。全仓库 grep `sign_with_root` 只有上述几处。
- `acmeserver.go:155` 有 `ca.Intermediate == nil && ash.Lifetime >= ca.IntermediateLifetime` 的检查。启用 `sign_with_root` 后，这个检查对中间证书生命周期的意义会变，但 JSON 路径本来就是这样，不是新增问题。
- 改动只影响 `acme_server` 的 Caddyfile 适配，对其他地方没有牵连。

【4 现有测试与约定】
- `caddytest/integration/caddyfile_adapt/tls_internal_options.caddyfiletest:6,46`：Caddyfile 里写 `sign_with_root`，输出 JSON 里是 `"sign_with_root": true`。这是仓库的参照约定。
- `acme_server_lifetime.caddyfiletest` 等一组文件格式固定：Caddyfile、`----------`、JSON。隐藏测试很可能是新增或修改这类适配测试，例如 `acme_server_sign_with_root.caddyfiletest`，断言 handler 输出里带 `"sign_with_root": true`。
- 输出 JSON 的字段顺序由 JSON 序列化决定，不需要手工处理。
- `caddytest/integration/acmeserver_test.go` 和 `pki_test.go` 是运行时集成测试，用来参考。
- 与题面期望没有冲突。

【5 边界与隐含要求】
- `sign_with_root` 不带参数：有多余参数时要返回 `h.ArgErr()`，与 internal issuer 一致。
- `parseACMEServer` 的 `lifetime` 分支在 81 行有潜在的空指针问题。如果 `lifetime` 写在 `ca` 之前，`ca` 为 nil，`ca.IntermediateLifetime` 会 panic。这是已有问题，与本题无关，但新增测试若把 `sign_with_root` 和 `lifetime` 组合使用要留意。
- 注释文档块里要补上这一项。
- 不要误把它加到 `pki ca` 子块里。JSON 里 `SignWithRoot` 属于 handler，不属于 CA。

【6 改动规模】
- 约 1 个文件、2 处改动：新增一个 case 和一行注释。
- 加上 1 个新测试文件的话是 2 个文件。
- 属于局部补丁，不需要新增结构，也不贯穿多层。

【7 难点一句话】
代码本身只是增加一个 case，几乎没有难度。难在题面的链接指向已经支持的 tls internal issuer，需要自己判断缺口在 `acme_server`；另外输出 JSON 的细节要和隐藏测试吻合。