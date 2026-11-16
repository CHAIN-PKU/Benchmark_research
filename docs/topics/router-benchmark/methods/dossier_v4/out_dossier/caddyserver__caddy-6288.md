# 仓库档案：Caddyfile 里 heredoc 和反引号写的 CEL 表达式报错

我没有复现，也没有找到确切的出错点，具体见第 7 节。

## 【1 题面要点】
- **期望行为**：具名匹配器可以省略 `expression` 关键字，直接写 heredoc 或反引号。
  - `@cel_tld_net <<CEL\n  {http.request.host.labels.0} == "net"\n  CEL`
  - ``@cel_tld_net `{http.request.host.labels.0} == "net"` ``
- **实际报错**：`wrong argument count or unexpected line ending after 'expression'`，版本为 2.8.0-beta.1。
- **对照**：显式写 `@x expression {…} == "net"` 可以正常工作。
- **题面没有给**：期望的 JSON 输出、修法建议、根因分析。题面只有最小的 Caddyfile 片段和错误信息。

## 【2 相关代码】
- `caddyconfig/httpcaddyfile/httptype.go:1386` 的 `parseMatcherDefinitions` 负责解析 `@name ...` 具名匹配器。
  - 1430-1442 行：第一个参数的 `Token().Quoted()` 为真时，认为省略了 `expression`。它会合成 `{Text:"expression", File:d.File(), Line:d.Line()}` 加原 token，调用 `makeMatcher("expression", …)`。
  - 1399 行的 `makeMatcher` 用这些 token 新建 Dispenser，并设置 `MatcherNameCtxKey`。
- `modules/caddyhttp/celmatcher.go:212` 的 `MatchExpression.UnmarshalCaddyfile` 负责解析 token。
  - 213 行：`d.Next()` 吃掉 `expression`。
  - 218-221 行：参数超过 1 个时用 `RemainingArgsRaw` 拼接，保留引号。
  - 224-233 行：恰好 1 个参数时，`NextArg` 加 `Val()`；`!NextArg` 就返回 `d.ArgErr()`。
  - `ArgErr` 的文案在 `dispenser.go:400`，与题面错误一致，所以报错发生在 224-226 行。
- `caddyconfig/caddyfile/dispenser.go:89-118`：`NextArg` 经 `nextOnSameLine`，由 `isNextOnNewLine` 判断下一个 token 是否换行。
- `caddyconfig/caddyfile/lexer.go:343-384`：`Quoted()` 为 `wasQuoted>0`。`NumLineBreaks` 对 heredoc 额外加 2。`isNextOnNewLine` 的判断是 `t1.Line+t1.NumLineBreaks() < t2.Line`。
- `dispenser.go:326` 的 `RemainingArgsRaw` 和 `:213` 的 `ValRaw` 是 2.8.0-beta.1 新加的，用来保留引号。

## 【3 并列与牵连】
- 同一个 `MatchExpression.UnmarshalCaddyfile` 还被这些入口调用：
  - 具名匹配器里显式写 `expression`。
  - 指令内联的 `expression` 匹配器。
  - `handle_errors` 在 `builtins.go:758-811` 自己拼表达式，走 JSON，不经 Unmarshal。
- `makeMatcher` 的合成 token 路径只有 1430-1442 行这一处。
- 修改 `UnmarshalCaddyfile` 或 Dispenser 的行判断，会影响所有使用 `expression` 的 Caddyfile 和 `matcher_syntax`、`expression_quotes` 等适配测试。
- 修改 `isNextOnNewLine` 或 `NumLineBreaks` 会波及整个 Caddyfile 解析，包括 import 和 heredoc。

## 【4 现有测试与约定】
- `caddytest/integration/caddyfile_adapt/expression_quotes.caddyfiletest:3-16` 覆盖了显式 `expression` 加引号、反引号、双引号、无引号。
  - 例如 `@e expression `{http.error.status_code} == 404``。
  - 它没有覆盖省略 `expression` 加反引号或 heredoc。
- `matcher_syntax.caddyfiletest` 和 `heredoc.caddyfiletest` 也涉及相关语法，我没有读它们的具体断言。
- `modules/caddyhttp/celmatcher_test.go` 有 `TestMatchExpressionUnmarshalCaddyfile` 之类的用例，用 `expression: &MatchExpression{...}`，从第 46 行起有多组，我没有逐条读。
- 约定在 `httptype.go:1428-1429` 的注释里：带引号的第一个 token 视为 `expression` 匹配器。
- 官方文档（题面链接）说明了 heredoc 和反引号是合法 token。
- 题面期望与这些约定一致，不冲突。

## 【5 边界与隐含要求】
- heredoc token 的 `Line` 是起始行，但内容跨多行。合成的 `expression` token 与它的相对行关系要对。
- 保留引号的语义：多 token 走 Raw，单 token 走 `Val`。
- 具名匹配器名要传给 `MatcherNameCtxKey`，`Name` 才不丢。
- heredoc 的缩进剥离要保持。
- 表达式里含 `"` 的字符串，例如 `== "net"`，在单 token 路径下不能被当作引号吃掉。
- 隐藏测试很可能是 `.caddyfiletest` 适配用例，或 Dispenser、celmatcher 的单测。

## 【6 改动规模】
大概率是局部修补，1-2 个文件、几行：
- `httptype.go:1434-1437` 合成 token 的方式。
- 或 `celmatcher.go:218-233` 的参数处理。
- 另有 1-2 个测试文件。
- 不需要新增结构。

## 【7 难点一句话】
报错只能出自 `celmatcher.go:224` 的 `ArgErr`，也就是 `NextArg()` 返回了假。静态读代码，我没能确认是哪个环节让合成的 `expression` token 与引号 token 被判成不同行或不同导入链。根因要靠写一个最小测试跑一遍才能定位，难点在定位，不在改动量。

我检查过的几处看起来都没问题：
- `Prev` 与 `CountRemainingArgs` 的配对。
- 合成 token 的 `File` 和 `Line`。
- 反引号词法。

没验证的怀疑点：
- 合成 `expression` token 的 `Line` 取 `d.Line()`，heredoc 起止行是否有偏差。
- 单个反引号参数是否被 `CountRemainingArgs` 与 `RemainingArgsRaw` 的组合干扰。
- 导入链字段 `imports`，合成 token 没带，而 `d.Token()` 带，两者长度可能不同，这会让 `isNextOnNewLine` 在 `len(imports)` 不等时直接返回 true。这是我最倾向的一个，但没有证据坐实。