## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
1. `markup/goldmark/blockquotes/blockquotes.go:240` 是题面指出的正则 `gitHubAlertRe`。`resolveGitHubAlert`（约第 244 行）已经用 `strings.ToLower` 处理了返回值，所以它本身能处理大小写。要核对的是匹配这一步，不要重复处理返回值。
2. 约第 96 行有另一处依赖：识别出 alert 后，它按第一个 `\n` 截掉 `[!NOTE]<br>` 前缀。先确认这个截取只依赖换行位置，不依赖标记的大小写或长度。
3. `alertType` 会通过 `AlertType()`（第 204 行）传给 render hook 模板。核对小写、混合大小写的输入传到模板里时，是不是仍然是固定的小写值。
4. 仓库里的文档和示例可能写着“只支持大写”。比如 `docs/` 下关于 blockquote render hook 的页面，可以搜 `[!NOTE]` 和 `alert`。有相关表述的话要一起核对。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
- `[!note]`、`[!Note]`、`[!nOtE]` 和全部五种类型（TIP、WARNING、IMPORTANT、CAUTION）的小写、混合大小写形式。
- 不应被匹配的输入：未知类型，比如 `[!foo]`；前面带普通文字的，比如 `x [!note]`；缺少右括号的；`[! note]` 这种括号内带空格的。
- 已有集成测试里有标记前后带空白的用例（见 `blockquotes_integration_test.go` 约第 52、59 行）。大小写改动后这些用例仍要通过。

**C. 仓库里已有的约定、文档或测试**
- `blockquotes_test.go` 里的 `TestResolveGitHubAlert` 是表驱动测试，输入以 `<p>` 开头。新增小写和混合大小写的用例要沿用这个格式。
- `blockquotes_integration_test.go` 里的 `render-blockquote-alert.html` 模板会输出 `.Type` 和 `.AlertType`。可以按同样的方式加一个小写输入的集成用例。
- 现有测试期望 `AlertType` 是小写，要保持这个约定。

**D. 提交前建议额外自测的情况**
1. 对五种类型各测大写、小写、混合大小写，确认 `resolveGitHubAlert` 都返回小写的类型名。
2. 对 `[!foo]`、`[!notes]`、`[!NOTE` 做负面测试，确认返回空字符串。
3. 跑一个端到端用例：`> [!note]` 加换行加正文。检查 `.Type` 是 `alert`，`.AlertType` 是 `note`，`.Text` 里没有残留 `[!note]`。
