# 仓库档案：Caddyfile 中 `between << >>` 被当成 heredoc

## 【1 题面要点】
- 期望行为：`templates { between <<  >> }` 能正常解析。`<<` 和 `>>` 应作为两个普通参数，成为模板分隔符。
- 复现：issue 给了 Caddyfile 片段，只有一个 `between <<  >>` 块。
- 实际报错：`heredoc marker on line #3 must contain only alpha-numeric characters, dashes and underscores; got '  >>'`
- 期望输出和修法建议：都没写。题面没提 `<<` 与 heredoc 的取舍，也没说是否要引号转义。

## 【2 相关代码】
- `caddyconfig/caddyfile/lexer.go:107-281`，`lexer.next()`，词法分析主循环。
- `lexer.go:139-164` 是 heredoc 起始检测，这是问题根源。
  - 条件是 `!inHeredoc && !heredocEscaped && len(val)>1 && string(val[:2])=="<<"`。
  - 此时 val 已有 `<<`，再读到下一个字符 ch：
    - 遇 `<` 就报 "too many '<'"（140-143）。
    - 遇 `\r` 就跳过。
    - 遇 `\n` 就把 `val[2:]` 当 marker，用 `heredocMarkerRegexp` 校验，失败则报题面那条错（151-156）。
    - 其余字符，包括空格，一律追加进 val（162）。
  - 本例中，`<<` 之后的空格和 `>>` 全被吞进 val，直到换行才当 marker 校验，所以得到 `'  >>'`。
- `lexer.go:222-246` 是空白分词逻辑。因为 heredoc 检测在它前面，所以读到 `<<` 后的空格根本走不到这里。
- `lexer.go:340`，`heredocMarkerRegexp = ^[A-Za-z0-9_-]+$`。
- `lexer.go:267-277` 是转义，`\<` 可以设置 `heredocEscaped` 来跳过 heredoc 语法。
- `lexer.go:283-322`，`finalizeHeredoc`，处理缩进剥离。
- `lexer.go:324-338`，`NumLineBreaks`，对 `wasQuoted=='<'` 的 token 加 2。
- `modules/caddyhttp/templates/caddyfile.go:43-47`，`between` 用 `h.RemainingArgs()` 取两个参数，要求恰好 2 个。这里不需要改，问题出在词法层。

## 【3 并列与牵连】
- 并列实现：没有。`<<` 只在 lexer 里处理。
- 其他位置：
  - `parse.go:578/585` 和 `dispenser.go:213-227` 只用到 `wasQuoted`。
  - `formatter.go` 里没有 heredoc 相关处理，我只用 grep 确认过没有匹配，没有细读。
- 影响面：lexer 是所有 Caddyfile 的入口，改 heredoc 判定会波及所有 `<<MARKER` 用法，包括 `caddytest/integration/caddyfile_adapt/heredoc.txt`（`respond <<EOF`）。
- 同类写法：任何形如 `<<` 或 `<<<` 后接空格的参数都有同样问题，例如 `{{`/`}}` 之外的自定义分隔符。

## 【4 现有测试与约定】
- `caddyconfig/caddyfile/lexer_test.go:253-405` 是 heredoc 用例，包括：
  - `heredoc <<EOF`、`<<VERY-LONG-MARKER` 等正常用法。
  - 单个 `<`：`heredoc <EOF` 当普通 token（325-336）。
  - `:369-374`：`heredoc <<HERE SAME LINE` 期望报错 `"heredoc marker on line #1 must contain only alpha-numeric characters, dashes and underscores; got 'HERE SAME LINE'"`。
  - `:377-383`：`<<<EOF` 期望 `"too many '<' for heredoc on line #1; only use two, for example <<END"`。
  - `:385-389`：未闭合的 heredoc 报错 `"incomplete heredoc <<EOF on line #3, expected ending marker EOF"`。
  - `:392-405`：缩进不匹配报错 `"mismatched leading whitespace in heredoc <<EOF on line #2 ..."`。
- 冲突点：`:369` 的用例与修复直接相关。
  - 它要求 `<<HERE SAME LINE` 在 marker 含空格时仍然报该错误。
  - 修复后 `<<  >>` 要被接受，所以这条要么保留、要么改，需要和新判定规则一起设计。
  - 如果隐藏测试改了这条的预期（比如不再报该错），就以隐藏测试为准。
- 外部规范：无，heredoc 是 Caddy 自定义语法。文档注释里也没找到针对 `<<` 的说明。
- 没有找到参考实现。

## 【5 边界与隐含要求】
- 需要区分真 heredoc 和普通 `<<` token。可能的判据：
  - `<<` 后面紧跟合法 marker 字符并以换行结束，才算 heredoc。
  - 遇到空白或非 marker 字符，则退化为普通 token。
- 需要保持原有行为：
  - `<<HERE SAME LINE` 这类现有用例的报错预期要么保留，要么随新规则调整。
  - `<<<EOF` 的 "too many '<'" 报错要保留。
- `<<` 后直接换行（marker 为空）怎么处理，当前代码会报 marker 不合法。
- `>>` 本身，以及 `<<` 在行尾、文件尾的情况。
- 行号计数（`l.line`、`skippedLines`）在退化为普通 token 时不能被破坏。
- `\r\n` 换行。
- 模糊点：`<<EOF` 后紧跟空格再跟别的参数是否也要放行。这决定了修复的判定规则，题面没说。
- 回退时，已消耗进 val 的字符必须原样成为 token，而 `<<` 之后遇到空白这一步本身要正确结束 token。

## 【6 改动规模】
- 主要改动：1 个文件 `lexer.go`，集中在 139-164 一处。
- 配套改动：`lexer_test.go` 加或改 1~2 个用例。
- 属于局部修补，不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
难点在于 heredoc 检测是和 token 累积交织在一起的流式状态机：要在读到空白或非 marker 字符时，把已吞入 val 的 `<<` 回退成普通 token。同时不能破坏现有 heredoc 的报错用例（尤其 `<<HERE SAME LINE` 那条）和行号计数。