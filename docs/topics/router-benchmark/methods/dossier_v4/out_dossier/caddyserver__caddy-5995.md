**档案：Caddy `uri replace "\}"` 无法匹配闭括号**

**【1 题面要点】**
- 要求的行为：Caddyfile 里 `uri replace "\}" %7D` 应和 `uri replace "\{" %7B` 一样生效，把查询串里的 `}` 替换成 `%7D`。
- 实际现象：`\{` 能替换，`\}` 不能替换。
- 复现：有。给出了 Caddyfile、docker-compose 和 curl 命令 `?test={%20content%20}`，并写了 `respond "{query}"`。
- 题面没有给出期望输出的原文，也没有给出修法建议。
- 题面援引了 Caddyfile 文档的转义规则，用 `\}` 转义大括号。

**【2 相关代码】**
- `replacer.go:132-244` `Replacer.replace`，是根因所在。
  - `replacer.go:136`：`if !strings.Contains(input, string(phOpen)) { return input, nil }`。输入里没有 `{` 就直接原样返回。
  - 输入是 `\}` 时没有 `{`，函数在 136 行提前返回，反斜杠没有被去掉。`find` 因此变成字面量 `\}`，在查询串里匹配不到。
  - 输入是 `\{` 时包含 `{`，会进入扫描循环。`replacer.go:155-159` 的转义处理会去掉反斜杠，得到 `{`，所以能匹配。
  - `replacer.go:180-187` 处理占位符内部的 `\}`；`replacer.go:354` 定义了常量 `phOpen, phClose, phEscape`。
- `modules/caddyhttp/rewrite/rewrite.go:416-436` `substrReplacer.do`。
  - `rewrite.go:426`：`find := repl.ReplaceAll(rep.Find, "")`，所以 `find` 经过 Replacer 处理。
  - `rewrite.go:427`：`replace` 同样经过 Replacer。
  - `rewrite.go:429-435`：用 `strings.Replace` 分别作用于 path 和 RawQuery。
- `modules/caddyhttp/rewrite/caddyfile.go:104-128` 解析 `uri replace`，把 `args[0]` 原样放进 `Find`。
- Caddyfile 词法层对 `\}` 的处理我没有逐行读，仅通过 `caddyfile.go` 的参数传递判断它不会替代 Replacer 层的反斜杠处理。

**【3 并列与牵连】**
- 改 `replace()` 会影响全仓库所有调用 `ReplaceAll`、`ReplaceKnown`、`ReplaceOrErr`、`ReplaceFunc` 的地方，包括日志、header、respond、rewrite 等。
- `rewrite.go:149,205,224,246,254,426,427,454` 都走同一个 Replacer，不需要分别修。
- 重点牵连：任何含 `\}` 但不含 `{` 的字符串，行为都会变，从保留反斜杠变成去掉反斜杠。
- `rewrite.go:454` 的 `regexReplacer` 只对 `Replace` 调了 `ReplaceAll`，`Find` 不经过 Replacer。这是并列实现，但不是本题的症状。
- `caddyconfig/httpcaddyfile/addresses.go:411-414` 有独立的转义逻辑，应该不受影响，但需要核对。

**【4 现有测试与约定】**
- `replacer_test.go:70-73` 是一条与题面直接冲突的现有断言：
  ```go
  input:  `\}`,
  expect: `\}`,
  ```
  修复后 `\}` 应得到 `}`，这条测试需要改，隐藏测试大概率也会改它。
- `replacer_test.go:66-69`：`foo\{bar\}` 期望 `foo{bar}`。
- `replacer_test.go:67-68`：单独的 `}` 期望 `}`。
- `replacer_test.go:126-129`：`{"json": "object"\}` 期望 `""`，因为占位符没有闭合，这是转义闭括号的既有语义。
- `replacer_test.go:159-162`：`{}{}{}{\\\\}\\\\` 期望 `{\\\}\\\\`，说明 `\\` 目前不被当作转义，只有 `\{` 和 `\}` 会被处理。
- `replacer_test.go:143-150`：占位符内部 `\{`、`\}` 的处理。
- `replacer_test.go:163-166`：含二进制字节和 `\}`（0x5C 0x7D）的用例，期望去掉反斜杠。这说明有 `{` 时 `\}` 本来就会被转义，没有 `{` 时才不会，行为不一致。
- 外部规范：Caddyfile 文档的转义规则，也就是题面链接。

**【5 边界与隐含要求】**
- 输入完全不含 `{` 但含 `\}`，例如 `\}`、`a\}b`、`\}\}`。
- 提前返回的判断需要放宽，同时要保留不含任何括号时的快速路径。
- `\}` 出现在字符串开头（`i == 0`）或结尾。
- 占位符内部的 `\}` 不能被误处理。例如 `{with \} brace}` 仍要按占位符键处理。
- 连续转义 `\}\}`。
- 去掉反斜杠后，`lastWriteCursor` 的记录要正确，避免丢字符或重复写入。
- 已有测试里 `\\` 不是转义，不能引入对它的新处理。
- 输入以 `\` 结尾，避免越界。

**【6 改动规模】**
- 核心修复：`replacer.go` 里 1 处，即 136 行的提前返回条件，可能还需要微调扫描循环。
- 测试：`replacer_test.go` 里改 1 条、新增几条用例。
- 局部修补，不需要新增结构，也不贯穿多层。预计改 1-2 个文件，几行代码。

**【7 难点一句话】**
根因就是 `replacer.go:136` 的提前返回，定位后改法很小，难点是改完后要保证 `\}` 在无 `{` 时去反斜杠，同时不破坏占位符内部转义、`\\` 等既有用例，并同步更新与之冲突的 `replacer_test.go:70-73`。