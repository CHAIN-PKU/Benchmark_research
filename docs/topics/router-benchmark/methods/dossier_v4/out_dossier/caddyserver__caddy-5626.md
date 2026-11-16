**档案：Caddy 嵌套 snippet import 在 handle 块内失效（beta.2 回归）**

下面的根因是我读代码推出来的，没有运行复现。

**【1 题面要点】**
- 要求的行为：snippet `responder` 内部再 `import responderWithStatus {args[0]} 202`，放在 `handle { import responder "foobar" }` 里，应当能逐层展开，并生成 `respond foobar 202`。
- 复现：题面给了完整 Caddyfile，没有期望输出，也没有修法建议。
- 报错原文：`parsing caddyfile tokens for 'handle': Caddyfile:12 - Error during parsing: unrecognized directive: import ... import chain: ['']`。
- 题面称 beta.1 正常、beta.2 回归，并引用了先前的 #4914。

**【2 相关代码】** 均在 `caddyconfig/caddyfile/` 下。
- `dispenser.go:457-478` `isNewLine()`：判断当前 token 是否在新行。上一个 token 的 File 不同则返回 true，否则比较 `prev.Line+prev.NumLineBreaks() < curr.Line`。
- `dispenser.go:483-504` `isNextOnNewLine()`：同样的逻辑，方向相反。
- `parse.go:567-613` `directive()`：在 handle 内收集 segment。第 595 行 `else if p.Val()=="import" && p.isNewLine()` 才会调用 `doImport(1)`。条件不满足时，`import` 会被当作普通 token 追加进 segment。后续 httpcaddyfile 就报 "unrecognized directive: import"。
- `parse.go:307-335` `directives()` 和 `parse.go:209-222` `addresses()`：同样依赖 `isNewLine()` 来识别 import。
- `parse.go:343-515` `doImport`：展开 snippet 并替换参数。第 509-512 行把 token 拼回 `p.tokens`，并把 cursor 回退 `len(args)+1`。

**推测的根因：**
- snippet token 的 File 就是 Caddyfile 本身，Line 是 snippet 定义处的行号（`import responderWithStatus` 在第 6 行）。
- 第一层展开后，这个 token 前面是 handle 的 `{`（第 11 行）。
- `isNewLine` 里 `prev.File != curr.File` 为假，`11 < 6` 也为假，于是返回 false。
- 所以嵌套的 `import` 没被识别。
- 只要 snippet 定义在调用点之后（行号更大），或者 snippet 内容来自别的文件，就不会触发。这与"定义在前、调用在后"的常见写法一致。

**【3 并列与牵连】**
- 三个调用点（`addresses`:216、`directives`:316、`directive`:595）都依赖 `isNewLine`。`directives` 的 316 行没有用 `isNewLine` 判断，只靠 `p.Val()=="import"`。
- `doImport` 第 467 行有一套独立的"行首判断"，同样用 File 和 Line 比较（`importedTokens[i-1].File != token.File || ... Line+NumLineBreaks() < token.Line`）。它用来识别 snippet 定义。
- `dispenser.go:120-135` `NextLine()` 用同一套 File/Line 比较。
- `isNewLine` 和 `isNextOnNewLine` 是成对方法，还影响 `{` 后同行 token 的检查（`parse.go:578,581,585`）。
- 修 `isNewLine` 会影响所有靠行号判断的地方，包括 `directive()` 的行尾判断（588 行）。
- 另一种修法是在 `doImport` 拼接 token 时给 token 标记"展开后行首"，这需要给 Token 加字段。

**【4 现有测试与约定】**
- `caddyconfig/caddyfile/parse_test.go:316-318` 有 import args 的用例，如 `import testdata/import_args0.txt a`。
- `parse_test.go:578-592` 是循环 import 报错的用例，写法是 `(A) {\n import A\n}`。我没有看到嵌套 import 在块内展开的用例。
- `caddytest/integration/caddyfile_adapt/import_args_snippet.txt` 等 3 个文件是黑盒适配测试。我只读了前 30 行，其中只有单层 snippet import，没有嵌套。
- 隐藏测试很可能是在 `caddyfile_adapt/` 下新增类似题面的 `.txt`，或在 `parse_test.go` 里新增嵌套 import 用例。
- 没有外部规范，行为以 beta.1 和 #4914 的修复为准。与题面期望不冲突。

**【5 边界与隐含要求】**
- 多层嵌套（3 层以上）要都能展开。
- `{args[0]}` 在内层传递并被再次替换。题面里内层是 `{args[0]} 202`，第一层替换后变成 `foobar 202`，第二层再替换。
- snippet 定义在调用点之前和之后两种顺序都要正常。
- 循环 import 检测不能被破坏，包括 snippetName 命名空间（`parse.go:432-441`）。
- 在 `handle` 之外（顶层、server block 内）的行为不能退化。
- 不能把同一行的 `import` 参数误当成新行指令，例如 `basicauth / import password`（`parse_test.go:769` 有此用例）。

**【6 改动规模】**
- 局部修补：1-2 个文件（`dispenser.go` 或 `parse.go`），大概 1-3 处。
- 另加一个集成测试 `.txt`。
- 不需要新增结构，除非选择给 Token 加标记字段的方案。

**【7 难点一句话】**
根因藏在"用行号加文件名推断新行"的启发式里，在 snippet 展开后行号顺序被打乱，需要在不破坏同行 `import` 参数判断和循环检测的前提下，让展开后的 token 仍能被识别为行首。