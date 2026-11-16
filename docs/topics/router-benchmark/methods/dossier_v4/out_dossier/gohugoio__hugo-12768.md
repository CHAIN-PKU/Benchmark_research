**仓库档案：Hugo alert 标题大小写问题**

已读：`blockquotes.go`、两个测试文件、`hooks.go`，并全仓搜索了 alert、AlertType 和 render-blockquote。快照不是 git 仓库，没有查看历史。

**【1 题面要点】**
- 期望行为：`[!note]`、`[!Note]`、`[!nOtE]` 都应像 GitHub 一样被识别为 alert。
- 现状：Hugo 只认全大写 `[!NOTE]`。
- 复现：题面只给了 markdown 片段 `> [!note]\n> Example`，没有期望的 HTML 输出。
- 修法建议（原句）：“Probably need to change this regex filter”，指向 `blockquotes.go` 里的 `gitHubAlertRe`（题面链接指向的是 v0.132.1 的行号 238）。
- 题面没有说明 `AlertType()` 对混合大小写输入该返回什么。

**【2 相关代码】**
- `markup/goldmark/blockquotes/blockquotes.go:240`：`var gitHubAlertRe = regexp.MustCompile(`^<p>\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION)\]`)`。这是大小写敏感的，也是根因。
- `blockquotes.go:244-250`：`resolveGitHubAlert(s)` 用该正则匹配，并对捕获组 `strings.ToLower`。所以只要正则放宽，返回值已经是小写。
- `blockquotes.go:82-85`：调用 `resolveGitHubAlert`，非空则 `typ = typeAlert`。
- `blockquotes.go:92-97`：对 alert 去掉前导行：`texts = "<p>" + texts[strings.Index(texts, "\n")+1:]`。它只依赖第一个换行，与大小写无关。
- `blockquotes.go:204`、`markup/converter/hooks/hooks.go:98-100`：`AlertType()` 的文档写明是 “converted to lowercase”。

**【3 并列与牵连】**
- 没有并列实现：`resolveGitHubAlert` 只被 `renderBlockquote` 一处调用，正则也只此一份。
- 全仓搜不到其他解析 `[!NOTE]` 的代码，`hugolib/page__per_output.go` 只是引用 hook 名称。
- 没有内置 alert 模板，只有用户模板或测试模板。
- 改动影响所有使用 `render-blockquote-alert.html` 的站点：原来被当作普通 blockquote 的 `[!note]` 会变成 alert。这是预期的行为变化。

**【4 现有测试与约定】**
- 单元测试 `blockquotes_test.go:22-60`：`TestResolveGitHubAlert` 是表驱动，调用 `resolveGitHubAlert("<p>"+test.input)`。
  - 断言：`"[!NOTE]"→"note"`，`"[!FOO]"→""`，用 `c.Assert(..., qt.Equals, ...)`。
  - 隐藏测试很可能增加 `[!note]`、`[!Note]` 之类的用例，期望值是小写。这与题面一致，无冲突。
- 集成测试 `blockquotes_integration_test.go:23-83`：`TestBlockquoteHook` 用 `hugolib.Test`，模板输出 `Blockquote Alert: |...|{{ .Type }}|`。
  - 现有用例覆盖 NOTE/TIP/CAUTION 后带空白、前导空格、属性和位置信息。
  - 断言如 `"Blockquote Alert: |<p>This is a tip.</p>"`，没有小写输入的用例。
- 约定：`hooks.go` 注释规定 `AlertType` 为小写。GitHub 的规范是大小写不敏感，所以应保持返回小写。

**【5 边界与隐含要求】**
- 正则要加 `(?i)`，或在匹配前先转小写。注意 `(?i)` 要放在 `^<p>` 之前或整体生效。
- 无效类型（如 `[!FOO]`）仍返回空。
- `<p>` 前缀和 `\]` 的严格匹配保持不变，不要放宽到 `[! note]` 这类形式。
- 返回值必须是小写，包括 `[!nOtE]` 这种混合大小写输入。
- 可选：更新 `blockquotes.go:237-239` 的注释，以及 docs 里“仅大写”的描述。快照里没有 docs 目录，这点未确认。

**【6 改动规模】**
- 核心修改：1 个文件 1 行（给正则加 `(?i)`）。
- 测试：在 `blockquotes_test.go` 的表里加几行，改动很小。
- 局部修补，不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
几乎没有难度：把正则改成大小写不敏感即可，`ToLower` 已存在，主要风险是漏掉 `(?i)` 的位置或让 `AlertType` 返回非小写值。