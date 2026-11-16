**【1 题面要点】**
- 要求的行为：`Layout/LeadingCommentSpace` 应当允许多行 shebang，也就是文件开头连续的 `#!` 注释行（例如 nix-shell 的 `#! nix-shell -i ruby --pure`）不再报 "Missing space after `#`."。
- 复现：题面给了一个 nix-shell 脚本，第 1 行是 `#!/usr/bin/env nix-shell`，后面三行是 `#! nix-shell ...`。它还给了实际输出：后三行各报一个 `C: [Correctable] Layout/LeadingCommentSpace: Missing space after #.`。
- 期望输出：这几行不报 offense。题面没有写成明确的期望输出。
- 修法建议（原句）："Perhaps LeadingCommentSpace could allow any comments at the top of the file to start with `#!` rather than just the first line?"
- 题面没有给出"顶部"的精确定义。它是否要求连续？中间能否夹空行或普通注释？这些都没说。
- 题面认为 `# rubocop:disable` 不可行，因为它会破坏 nix 对 shebang 的解析。

**【2 相关代码】**
- `lib/rubocop/cop/layout/leading_comment_space.rb:95-110`：`on_new_investigation` 遍历 `processed_source.comments`。
  - 第 97 行的正则 `/\A(?!#\+\+|#--)(#+[^#\s=])/` 判断注释是否缺少空格。
  - 第 98 行 `next if comment.loc.line == 1 && allowed_on_first_line?(comment)` 是现在只放过第 1 行的地方，也是最可能要改的位置。
- `leading_comment_space.rb:118-120`：`allowed_on_first_line?` 返回 `shebang?(comment) || (rackup_config_file? && rackup_options?(comment))`。
- `leading_comment_space.rb:122-124`：`shebang?` 是 `comment.text.start_with?('#!')`。
- `leading_comment_space.rb:126-132`：`rackup_options?` 检查 `#\`，`rackup_config_file?` 检查文件名是否为 `config.ru`。
- 第 104-108 行是 autocorrect：在 `#` 后插入一个空格。
- 第 6-10 行的类文档提到了 "shebang" directives。

**【3 并列与牵连】**
- 同类 shebang 判断在别处各自实现，没有共享的 helper：
  - `line_length.rb:189-191` 的 `shebang?` 是 `line_index.zero? && line.start_with?('#!')`，只认第 1 行。
  - `lint/script_permission.rb:37-42`、`style/encoding.rb:18,34`、`style/frozen_string_literal_comment.rb:97,139`、`style/copyright.rb:74-79`，都只看第 1 行或第 1 个 token。
- 这些都不属于本 issue 的范围，题面只提 LeadingCommentSpace。多行 shebang 在 LineLength 里仍会按普通注释检查长度，那条 nix 的 `-I nixpkgs=...` 行很长，这可能是后续问题，但题面没要求。
- 同一个 cop 里 `rackup_options?`（`#\`）也只限第 1 行。是否一并放宽？题面没提，推测不改。
- 改动只影响 LeadingCommentSpace 自身。它没有被其他 cop 调用。
- 要同步的非代码文件：
  - `changelog/` 下要新增一个条目，格式见 `changelog/fix_allow_to_write_generics_type_of_rbs__inline.md`，是单行 `* [#PR](url): 描述. ([@user][])`。
  - 类文档注释（`leading_comment_space.rb:6-10`）。
  - `docs/modules/ROOT/pages/cops_layout.adoc` 由文档注释生成，一般无需手改。
  - `config/default.yml:1032-1041` 的 `VersionChanged` 通常由维护者在发版时处理。

**【4 现有测试与约定】**
- 测试文件：`spec/rubocop/cop/layout/leading_comment_space_spec.rb`。
  - 第 31-36 行：`'does not register an offense for #! on first line'`，断言 `expect_no_offenses("#!/usr/bin/ruby\ntest")`。
  - 第 38-49 行：`'registers an offense and corrects #! after the first line'`，源码是 `test\n#!/usr/bin/ruby`，断言第 2 行报 offense，并修正为 `# !/usr/bin/ruby`。
  - 第 51-71 行：config.ru 下 `#\` 只在第 1 行允许，第 2 行报 offense。
  - 第 73-92 行：非 config.ru 文件里 `#\` 在任何行都报 offense。
- 与题面的关系：
  - 第 38-49 行的行为要保留，也就是代码之后的 `#!` 仍然是 offense。
  - 隐藏测试很可能新增类似这样的用例：`#!/usr/bin/env nix-shell\n#! nix-shell -i ruby --pure\n...` 不报 offense。
  - 现有测试里没有 shebang 之后紧跟 `#!` 的用例，所以不冲突。
- 外部规范：shebang 本身只有第 1 行有 OS 层面的意义。多行 shebang 是 nix-shell 等工具的约定，仓库内没有参考实现。

**【5 边界与隐含要求】**
- "顶部"的定义需要选择：
  - 连续的 `#!` 行：第 1 行是 shebang，后面紧跟的行也是 `#!`。这是最保守的做法。
  - 题面字面的"文件顶部的任意注释"：允许中间夹空行、普通注释或 magic comment。
  - 第 1 行不是 `#!` 时，第 2 行的 `#!` 怎么处理，需要决定。现有测试 `test\n#!/usr/bin/ruby` 要求报 offense，但那是代码行之后。
- 具体要处理的情况：
  - 空行是否打断连续性。
  - shebang 之间夹了普通注释。
  - 行尾注释（`foo #!bar`）不能算顶部 shebang。
  - 以 `#!` 开头的内容出现在代码之后，必须仍然报 offense。
  - 实现要用行号或 token 位置判断，而不是靠注释出现的顺序。
- 同一个 `on_new_investigation` 里，AllowDoxygen、Gemfile、RBS、Steep 的 `next if` 顺序不能被破坏。
- 该方法已经带有 `rubocop:disable Metrics/AbcSize, CyclomaticComplexity, PerceivedComplexity`。新增逻辑最好放进私有 helper，以免触发仓库自己的 rubocop 检查。

**【6 改动规模】**
- 约 1 个源码文件，改 1-2 处：`leading_comment_space.rb` 的第 98 行，加上 `allowed_on_first_line?` / `shebang?` 的小改或新增 helper。
- 另有 1 个 spec 追加用例，1 个 changelog 文件。
- 属于局部修补，不用新增结构，也不贯穿多层。

**【7 难点一句话】**
代码本身很简单。难点在于题面没有定义"顶部"的范围（连续 `#!` 行，还是任意顶部注释），要选一个既能让隐藏测试里的多行 shebang 通过，又保证第 2 行 `test\n#!...` 仍然报 offense 的判定规则。