# 档案：bat 的 `--map-syntax` 区分大小写（Windows 上 `NuGet.Config` 不着色）

我没有运行测试，也没有构建，结论都来自读代码。

## 【1 题面要点】
- 期望行为：用户用 `--map-syntax='*.config:XML'` 映射后，`NuGet.Config` 和 `NuGet.config` 都应按 XML 着色。issue 原文是 "The file is displayed with syntax coloring."
- 现象：只有扩展名大小写与映射模式完全一致时才着色。
- 复现：有。用 `--map-syntax='*.config:XML'`，对比 `bat NuGet.Config` 和 `bat NuGet.config`。
- 修法建议：没有。
- 题面没有说明是否只在 Windows 上生效，也没有给期望输出的字节串。

## 【2 相关代码】
- `src/syntax_mapping.rs:212-219` `SyntaxMapping::insert`
  - 用 `GlobBuilder::new(from).case_insensitive(false).literal_separator(true).build()`。
  - 用户映射和内置映射都经过这里。
  - **根因最可能在 :214。**
- `src/syntax_mapping.rs:225-245` `get_syntax_for`
  - 按逆序遍历 `mappings`，所以后加入的用户映射优先。
  - 先用完整路径匹配，再用 `file_name` 匹配。
  - 之后去掉 ignored suffix，递归调用自身。
- `src/assets.rs:201-236` `get_syntax_for_path`
  - 优先级依次是：MapTo/MapToUnknown、syntect 按文件名匹配、MapExtensionToUnknown、syntect 按扩展名匹配。
  - `find_syntax_by_extension`（:301）交给 syntect。syntect 对扩展名已经不区分大小写。
- `src/assets.rs:257-289` `get_syntax`
  - 路径检测失败时回退到首行检测。
- `src/bin/bat/app.rs:128-136`
  - 解析 `glob:syntax`，调用 `insert(parts[0], MapTo(parts[1]))`。

## 【3 并列与牵连】
- 单点：只有 `insert` 一处构造 `GlobBuilder`，`case_insensitive` 只出现一次（grep 结果）。
- 内置映射也走 `insert`（:43-205），例如 `*.h`、`*.fs`、`*.conf`、`build`、`Containerfile`、`**/.ssh/config`、`**/bat/config`、git config 路径，以及 `/etc/` 下的 nginx、apache 路径。
  - 把大小写改成不敏感后，这些内置映射也会变成不敏感。
  - 路径型映射在 Linux 上本应区分大小写，例如 `/etc/profile`。
  - `build` 和 `rails` 是 MapToUnknown，现在只匹配小写。不敏感后，名为 `Build` 的文件也会被当成未知语法。
  - 这些内置映射的覆盖范围会随之改变。
- `src/bin/bat/main.rs:81-92` `get_syntax_mapping_to_paths` 和 `--list-languages` 会显示 `matcher.glob().glob()`。glob 字符串不变，显示不受影响。
- `no_duplicate_builtin_keys` 测试（`syntax_mapping.rs:303`）比较 `glob()`，不受影响。
- ignored suffix 路径（`get_syntax_for` :239-244）递归调用同一个 `get_syntax_for`，随 `insert` 一起生效。
- 文档：`README.md:569-592` 描述了 `--map-syntax`。`clap_app.rs:346-353` 的帮助文本写着 "The glob pattern is matched against the full path and the filename"，没有提到大小写。
- `CHANGELOG.md` 的 unreleased 区有 Bugfixes 小节，通常需要加一条。

## 【4 现有测试与约定】
- `src/assets.rs:651-669` `syntax_detection_is_case_insensitive`
  - 断言 `test.syntax_for_file("README.md"/"README.mD"/"README.Md"/"README.MD") == "Markdown"`。
  - 再 `insert("*.MD", MapTo("Markdown"))` 后断言结果不变。
  - 约定已经明确：syntect 的内置扩展名匹配不区分大小写（CHANGELOG:118 "File extensions are now matched case-insensitively. See #1854, #2181"）。
  - 但**没有覆盖用户 `--map-syntax` 的大小写**，所以与题面不冲突，只是没覆盖。
  - 隐藏测试很可能在这里加断言，比如用 `*.myext` 或 `*.MD` 映射后匹配 `.Md` 或 `.MD`。
- `src/syntax_mapping.rs:255-299` 测试
  - `basic`：`get_syntax_for("/path/to/Cargo.lock")`。
  - `user_can_override_builtin_mappings`：`/etc/profile`。
  - `builtin_mappings`：`/path/to/build` 返回 `MapToUnknown`。
  - 都是小写路径，大小写不敏感后不会失败。
- `src/assets.rs:554-573` `syntax_detection_same_for_inputkinds`：`*.myext`、`MY_FILE`。MY_FILE 是全大写的精确文件名映射。
- `tests/integration_tests.rs:1626-1655`、`:2047-2074`：`--map-syntax` 的集成测试，包含用 ignored suffix 的 `*.demo:JSON`。断言的是着色字节串。
- 没有找到 Windows 专用或平台相关的大小写约定。
- 参考：ripgrep/globset 提供 `GlobBuilder::case_insensitive(true)`，这是标准 API。

## 【5 边界与隐含要求】
- 是只对扩展名不敏感，还是整个 glob 都不敏感，题面没说。整个 glob 不敏感，会让路径部分（如 `/etc/...`）在 Linux 上也变得不敏感。
- 精确文件名映射（`MY_FILE`、`.ignore`、`Containerfile`、`build`）要不要不敏感，没有规定。
- 同一个 glob 同时注册大小写两种形式（如 `*.md` 和 `*.MD`）时，行为要保持稳定，现有测试里有这种情形。
- 用户映射与内置映射的顺序要保持：用户映射后插入，逆序遍历时仍然优先。
- MapExtensionToUnknown（`*.conf`）也会随之变成不敏感。`Foo.CONF` 会回退到首行检测。
- Windows 路径的反斜杠分隔符，`literal_separator(true)` 要保留。
- 路径经 `PathAbs` 处理（assets.rs:274）后再匹配，绝对路径会参与匹配。
- 用户映射要同时匹配文件名形式（`Candidate::new(file_name)`）。

## 【6 改动规模】
- 最小修改：`syntax_mapping.rs:214` 一行（`false` 改 `true`），外加 1 到 2 个测试和一条 CHANGELOG。属于局部修补。
- 如果要区分内置与用户映射，或只对扩展名不敏感，则需要给 `insert` 加参数或新结构，并改 `app.rs` 调用点。这会明显变大，但题面没有要求。

## 【7 难点一句话】
定位本身很容易，根因就是 `GlobBuilder.case_insensitive(false)`。难点在于判断全局改成不敏感对内置的路径型映射（如 `/etc/...`）和 `build`、`rails` 这类 MapToUnknown 映射的副作用，以及在这些副作用之间取舍。