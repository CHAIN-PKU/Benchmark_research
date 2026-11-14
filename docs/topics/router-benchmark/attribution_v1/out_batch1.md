# DS 挂因分析 batch1（4 题）

## 1. axios__axios-5316（Node 18 全局 FormData 报错）
1. 题目要什么：用 Node 18 自带的全局 `FormData` 作为请求体时，axios 报 "Data after transformation must be a string, ArrayBuffer, Buffer or Stream"，希望支持它。
2. 标准答案：在 `lib/adapters/http.js` 新增 `utils.isSpecCompliantForm` 分支，用新文件 `helpers/formDataToStream.js` 把 spec 兼容的 FormData 编成 multipart 流（含边界、Content-Length、文件名转义），同时加 `readBlob.js`、Blob 分支、`lib/env/classes/FormData.js` 优先用全局 FormData；**package.json 新增 devDependency `formdata-node`**（测试要 import）。
3. DS 两次：
   - run1：新增 `helpers/formDataToStream.js`（自写 173 行，PassThrough 流逐段写入）+ http.js 里 `else if (utils.isFormData(data)) data = formDataToStream(...)`。
   - run2：在 http.js 里写 `convertFormData`，把全局 FormData 转成 `form-data` 包实例（Blob 用 `Readable.fromWeb`），并在 utils 加 `isSpecCompliantForm`（名字与标准答案一致）。
   - 两次挂的方式完全相同：三个测试（F2P 1 个 + P2P 2 个）全部失败，输出为 `ERR_MODULE_NOT_FOUND: Cannot find package 'formdata-node' imported from test/unit/adapters/http.js`，即测试文件根本没加载。
4. 挂因：证据显示是测试文件 import 的 `formdata-node` 包在评测环境没装（标准答案的 package.json 改动才加这个依赖，DS 不会、也没理由去加）。所以两次的 DS 改法对错**无法由这次结果判断**；连原本应通过的 P2P 都挂，说明不是行为问题。DS 自己在最终报告里也说仓库自带测试在沙箱里因 ECONNREFUSED 跑不了，只做了手工验证。两次实现思路都合理（run2 甚至与标准答案同名 helper），但没有被真正检验。
5. 类别：**F（环境/测试执行问题）**；副类别 G（评测依赖应由补丁声明 package.json，属于"隐藏要求"，可算 E 的变体）。
6. 动手前信号：题面和仓库里看不出对 DS 难；唯一间接线索是"这是新功能（支持 FormData 类型）而非 bug 修复，测试会用到新写法/新依赖"——但这只能事后推断。基本「看不出」，应作为无效样本剔除。
7. 把握：高（对"F"）；对 DS 代码本身是否正确：低（未验证）。

## 2. axios__axios-6539（CVE-2024-39338 SSRF，协议相对 URL）
1. 题目要什么：`baseURL` 已配置时，`get('//google.com')` 这种协议相对路径被当成绝对 URL，绕过 baseURL 请求别的主机；要修掉。
2. 标准答案：只改 `lib/helpers/isAbsoluteURL.js` 一个正则，去掉 `//` 开头算绝对 URL 的分支（`^([a-z][a-z\d+\-.]*:)\/\//i`）。这样 `//localhost:4667` 被当作普通路径拼到 baseURL 后面，请求仍发给 good server（`responseUrl = base + '/localhost:4667'`）。
3. DS 两次：
   - run1：http.js 里 `new URL(fullPath, platform.hasBrowserEnv ? platform.origin : undefined)`。
   - run2：`new URL(fullPath, platform.hasBrowserEnv ? 'http://localhost' : undefined)`。
   - 两次都只改一行，都挂在唯一 F2P "Server-Side Request Forgery (SSRF) should not fetch bad server"：`TypeError: Invalid URL at dispatchHttpRequest (http.js:232)`。
4. 挂因：DS 选了题面里"Expected behavior"明确写的方案——让协议相对 URL 在服务端直接报 ERR_INVALID_URL（恢复 1.3.2 之前行为）。但测试期望的是另一种方案：不报错，把 `//x` 当路径拼到 baseURL（题面里 "Developer might also have expected: config.url: https://userapi.example.com//www.google.com/" 只是轻描一句）。测试断言 `response.data === 'good'`，DS 的请求抛异常，直接失败。同时 DS 的改法还会让"无 baseURL 的相对路径"在 Node 里也抛错（run2 自己验证过 `//google.com` 无论有无 baseURL 都报错），范围更宽。两次对比：无本质差别。
5. 类别：**E（题面信息不足/与测试期望不一致，题面给了两种合理方案，测试只认其中一种）**；副类别 A（正确修法在更靠上游的 isAbsoluteURL，而不是 URL 解析处）。
6. 动手前信号：题面里"Expected behavior"写"An error could be raised"，同时又列了"Developer might also have expected"的另一种输出——出现多种可接受行为本身就是风险信号；另外题面是 CVE 报告而不是复现测试，没有指定期望行为的唯一性。若 DS 去读仓库，可看到 `isAbsoluteURL.js` 里注释明说 `//` 算绝对，且 `test/specs/helpers/isAbsoluteURL.spec.js` 有"protocol-relative 返回 true"的既有用例——这是"测试大概率要翻转这条既有约定"的线索。较具体但不强。
7. 把握：高。

## 3. caddyserver__caddy-6051（heredoc 允许空行）
1. 题目要什么：Caddyfile 的 heredoc 里，空行不应因为缺少与结束标记相同的缩进而报 "mismatched leading whitespace"。
2. 标准答案：`lexer.go finalizeHeredoc` 里逐行处理时，`if lineText == ""`（真正的空串）才追加 "\n" 并跳过；仅含空白的行仍走原来的缩进匹配。
3. DS 两次：两次几乎一样，都在同位置加 `if strings.TrimSpace(lineText) == "" { out += "\n"; continue }`，各自在 lexer_test.go 加了一个"空行"用例，自己跑过 `go test` 通过。结果都挂在 TestLexer（其它 P2P 全过）。
4. 挂因：DS 把"空行"扩成"空行或只含空白的行"。隐藏测试有新用例 "blank line with one tab"（case 47）：行内只有一个 `\t`、无缩进的 heredoc，期望保留为 `"...\n\t\n..."`；DS 的 TrimSpace 把它吞成 `"\n\n"`，输出里 `\t` 丢失（测试输出：expected 含 tab 行，but was 空行）。另一个用例（缩进少一格的空白行应继续报 mismatched 错误）DS 也会漏报。即：DS 的改法"过度通用"，改变了空白行的既有语义。
5. 类别：**A（正确修法要更窄/精确，DS 泛化过头）**；副类别 E（题面只说"blank line"，未说明只含空白的行如何处理）。
6. 动手前信号：题面里作者自己提到 "I can add a whitespace before a blank line but `caddy fmt` will remove it" 和 "skip whitespace stripping on a blank line"——暗示"带空白的空行"和"真空行"是两种情形，需要区分；仓库里已有 heredoc 的错误信息测试（"mismatched leading whitespace ... [        content]"），说明既有逻辑对空白很讲究。若 DS 去看 lexer_test 已有用例会发现"空白必须精确匹配"是核心约定。信号中等偏弱。
7. 把握：高。

## 4. caddyserver__caddy-6115（sticky cookie 默认 Secure + SameSite=None）
1. 题目要什么：`lb_policy cookie` 设的粘性 cookie 默认带 `SameSite=None`（题面标题还有 Secure），使第三方链接进来也能带 cookie。
2. 标准答案：构造 cookie 后，**只在请求是 HTTPS 时**（`req.TLS != nil`，或受信代理且 `X-Forwarded-Proto: https`）才设 `Secure=true` 且 `SameSite=None`；明文 HTTP 请求保持 `Secure=false`、不设 SameSite。
3. DS 两次：两次产品代码完全相同——无条件改成 `Secure: true, SameSite: http.SameSiteNoneMode`。run2 还顺手改了现有 `TestCookieHashPolicy`，加上断言"Secure 必须为 true"（与隐藏测试相反）。两次 F2P `TestCookieHashPolicyWithSecureRequest` 都过，但 P2P `TestCookieHashPolicy` 都挂：`selectionpolicies_test.go:662: cookieHashPolicy should set cookie Secure attribute to false when request is not secure`。
4. 挂因：改法不分请求是否安全，一律 Secure+None。浏览器会拒绝 HTTP 上的 `Secure` cookie，所以明文请求下粘性会失效，这既是行为缺陷，也撞上了隐藏测试对"非安全请求保持 Secure=false"的新断言。DS 在 run1 声称 `TestCookieHashPolicy` 通过（原测试没断言此项，所以确实通过），没有想到要区分 http/https；run2 更是把旧测试改成匹配自己的实现。注意：题面标题说"Secure and SameSite=None by default"，字面上 DS 的做法是照题面做的，"仅 HTTPS 时"是题面没写的隐藏条件。
5. 类别：**E（题面信息不足：未说明仅 HTTPS 时设置）**；副类别 A（正确修法需按请求条件判断，更通用/更严谨）、D（改坏了老测试的语义，虽然老测试被隐藏测试的新断言收紧）。
6. 动手前信号：看题面+仓库可预见的线索：(a) `Secure=true` 的 cookie 在 HTTP 下浏览器不会保存/回传——这是通用 Web 知识，也能触发"应区分协议"的疑问；(b) 题面示例里 curl 访问的是 https，但 caddy 也常被放在 TLS 终止代理后面，仓库里已有 `TrustedProxyVarKey`、`X-Forwarded-Proto` 的处理先例（`lastHeaderValue`）；(c) 仓库里已有 `TestCookieHashPolicy`，对 cookie 属性有测试——改默认值必然碰到它。DS 两次只用了 6~11 轮、一两分钟就收工，说明没有深挖。信号弱到中等。
7. 把握：高（行为与证据一致）；对"信号"一项：中。

## 汇总
- 5316：F（环境缺 formdata-node，应剔除样本）
- 6539：E（题面给两种方案，测试只认"拼到 baseURL"）+A
- 6051：A（TrimSpace 泛化过头，吞掉只含空白行）+E
- 6115：E（仅 HTTPS 才 Secure/None）+A/D
