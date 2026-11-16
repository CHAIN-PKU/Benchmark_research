**【1 题面要点】**
- 期望行为：`--map-syntax` 和 `--ignored-suffix` 要能叠加使用。`bat foo.demo.example --map-syntax "*.demo:YAML" --ignored-suffix ".example"` 应当按 YAML 高亮。
- 现状：只加 `--map-syntax "*.demo:YAML"` 时 `foo.demo` 能高亮。只加 `--ignored-suffix` 配合内置映射时 `foo.yaml.example` 也能高亮。两者合用时 `foo.demo.example` 不高亮。
- 题面给了复现步骤，也给了期望，原话是 “I expect it can print `foo.demo.example` with YAML syntax.”。
- 题面没有给修法建议，也没有给期望输出的具体字节。

**【2 相关代码】**（路径相对仓库根）
- `src/assets.rs:201-236` `get_syntax_for_path`：
  - 第 208 行 `mapping.get_syntax_for(path)` 只拿完整路径去匹配用户或内置的 glob，不会剥后缀。
  - 命中 `MapToUnknown` 时直接返回 `UndetectedSyntax`。命中 `MapTo` 时直接查名字并返回。
  - 第 220-235 行才用 `ignored_suffixes` 做 syntect 的文件名和扩展名查找。这里只在 syntect 的内置扩展名里递归剥后缀，不会再查 `mapping`。
  - `foo.demo.example` 的完整路径不匹配 `*.demo`，syntect 也不认识 `.demo`，所以失败。
- `src/assets.rs:309-339` `get_syntax_for_file_name` 和 `get_syntax_for_file_extension`：
  - 两个并列的递归函数，分别按“整个文件名当扩展名”和“真正的扩展名”查 syntect。
  - 都通过 `ignored_suffixes.try_with_stripped_suffix` 递归。
- `src/syntax_mapping/ignored_suffixes.rs:38-65`：
  - `strip_suffix` 只剥一层，遇到第一个匹配的后缀就返回。
  - `try_with_stripped_suffix` 接收闭包 `Fn(&'a OsStr) -> Result<Option<T>>`，只剥不匹配。
- `src/syntax_mapping.rs:193-206` `get_syntax_for`：
  - 对完整路径和文件名各做一次 glob 匹配，按插入逆序，后插入的优先。
  - 它是 `pub(crate)`，只有一个非测试调用点，在 `assets.rs:208`。
- `src/syntax_mapping.rs:30-34`：`ignored_suffixes` 是 `SyntaxMapping` 的字段，所以 `get_syntax_for` 里能直接访问它。
- `src/bin/bat/app.rs:110-112`：把 CLI 的后缀加进 `SyntaxMapping`。

**【3 并列与牵连】**
- `get_syntax_for_file_name` 和 `get_syntax_for_file_extension` 是并列实现。如果改成“剥后缀后再查 mapping”，两条路径都要考虑。
- `get_syntax_for_path` 的调用点：
  - `src/assets.rs:174`：弃用的 `syntax_for_file_name`。
  - `src/assets.rs:273`：`get_syntax` 的主路径，用于所有输入。
  - `src/bin/bat/main.rs:110`：`--list-languages` 里用测试文件判断某语言是否被映射。
- `get_syntax_for` 是 `pub(crate)`，改签名只影响 `assets.rs:208` 和 `syntax_mapping.rs` 里的单元测试（第 222、225、228、238、244、254 行）。
  - 如果隐藏测试沿用这些调用，就不能随意改它的签名或返回类型。
- `MapToUnknown` 和 `MapExtensionToUnknown` 的语义也会受牵连。比如 `foo.conf.bak` 是否应按 `*.conf` 走 `MapExtensionToUnknown`。
- `mappings()` 被 `main.rs:117` 使用，改动时不应破坏它。

**【4 现有测试与约定】**
- `tests/integration_tests.rs:1439-1473` `ignored_suffix_arg`：
  - 断言 `test.json~` 带 JSON 高亮。
  - 断言 `--ignored-suffix=.suffix` 时 `test.json.suffix` 带 JSON 高亮。
  - 断言不带该参数的 `test.json.suffix` 输出为 `{"test": "value"}`，无高亮。
  - 这三条与题面期望不冲突。
- `src/syntax_mapping/ignored_suffixes.rs:67-107` 有单元测试 `internal_suffixes` 和 `external_suffixes`。它们调用 `try_with_stripped_suffix(file_name, |s| Ok(Some(s)))`，断言返回 `test.json`。
  - 这两个测试把 `try_with_stripped_suffix` 的签名固定下来了，隐藏测试很可能沿用。
- `src/syntax_mapping.rs:213-257` 的单元测试覆盖 `get_syntax_for`，比如 `map.get_syntax_for("/path/to/Cargo.lock")`。
- `assets.rs:190-199` 的文档注释写明了 `MapToUnknown` 和 `MapExtensionToUnknown` 的优先级：
  - 内置语法对文件名的识别，优先于 `MapExtensionToUnknown`。
  - 这是现有约定，修复不应破坏它。
- 仓库里没有集成测试同时用 `--map-syntax` 和 `--ignored-suffix`。

**【5 边界与隐含要求】**
- 剥后缀后既要查用户 mapping，也要保留原有的 syntect 内置查找。
- 优先级需要定：先试完整路径的 mapping，再试剥后缀后的 mapping，再试 syntect。现有的 `MapTo` 命中立即返回的行为要保持。
- 多层后缀（`foo.demo.bak.example`）：现有 `strip_suffix` 只剥一层，递归后才能剥多层。新逻辑也应递归。
- 剥后缀后得到的路径可能要保留目录部分，因为 glob 如 `/etc/nginx/**/*.conf` 依赖完整路径。如果只传文件名，带目录的 glob 会失效。
- 剥后缀后命中 `MapToUnknown`（如 `build.bak`）应返回 `UndetectedSyntax` 并回退到首行检测。
- `try_with_stripped_suffix` 现在要求 `&'a OsStr` 并且闭包是 `Fn`。如果要传路径，生命周期或类型可能要调整。
- 剥掉后缀后文件名为空的情形（文件名恰好等于后缀）。

**【6 改动规模】**
- 核心改动只在 `src/assets.rs` 的 `get_syntax_for_path` 和相关递归，可能还要碰 `src/syntax_mapping.rs` 或 `ignored_suffixes.rs`。预计 1 到 3 个文件，改动几十行以内。
- 属于局部修补，不用新增结构，也不贯穿多层。
- 通常还要补一个集成测试，和可能的 `CHANGELOG.md` 条目。

**【7 难点一句话】**
- 难点不在定位，而在设计递归与优先级：剥后缀后要重新走 mapping 的 glob 匹配，又不能破坏 `MapToUnknown`、`MapExtensionToUnknown` 的现有语义，同时要保持 `try_with_stripped_suffix` 和 `get_syntax_for` 现有签名，以兼容单元测试。