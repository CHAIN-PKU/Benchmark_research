## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
- `src/printer.rs` 里 `InteractivePrinter::print_header` 的 `HeaderFilename` 分支（约第 384–393 行）。它直接 `writeln!` 整个 `description.title()`，没有按终端宽度折行。这里是主要修改点。
- 同一函数里每个 header 组件都先调用 `print_header_component_indent`（约第 290 行）。它输出的缩进是 panel 宽度加 `│ `。折行后的每一行都需要同样的缩进，所以要核对续行能否复用它。
- 同一函数的 `HeaderFilesize` 分支和 `mode` 后缀（`   <BINARY>`、`<EMPTY>` 等）在文件名之后输出。文件名折行后，这两项的位置和换行是否正确，也要一并检查。
- `description.kind()` 的前缀（`File: ` 等）占用了第一行的宽度。第一行可用宽度因此小于后续行，折行时要把前缀长度算进去。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
- 文件名恰好等于可用宽度、比可用宽度少 1、多 1。这是折行与否的分界，容易出现差一错误。
- 非 ASCII 或宽字符（CJK、emoji）的路径。仓库已引入 `unicode-width`，`printer.rs` 里也在用 `UnicodeWidthChar`。`len()` 按字节算、`chars().count()` 按字符算，两者都不等于显示宽度。
- 极窄的终端，或 `panel_width` 为 0 的情形（没有行号、没有 grid）。可用宽度可能很小，要避免死循环或下溢。注意 `config.term_width` 在不同样式下的取值。
- 带 `<BINARY>` 等后缀的文件名，以及 stdin 的 `STDIN` 标题。后者没有 kind 前缀的情况也要考虑。

**C. 仓库里已有的约定、文档或测试中需要遵守或核对的地方**
- 同一文件里 `print_horizontal_line`、`create_fake_panel`、`print_snip` 对宽度的处理方式（例如 `term_width - (panel_width + 1)`）。可以参考它们对 panel 和 grid 的宽度约定。
- `src/printer.rs` 约第 194–210 行：`panel_width` 的计算，以及终端过窄时 panel 被置 0 的逻辑。
- `tests/snapshots/`（包括 `output/`、`generate_snapshots.py`）和 `tests/integration_tests.rs` 里的 header 相关用例。现有输出不应改变，短路径的输出要保持原样。
- `CHANGELOG.md` 顶部的 Bugfixes 段是仓库约定的记录位置，可以按已有条目格式补一条。

**D. 建议提交前额外自测的情况**
1. 用 `--terminal-width` 指定较小宽度，分别在默认样式、`--style=header,grid` 和 `--style=header`（无行号）下运行长路径。检查每个续行的缩进是否对齐，grid 竖线是否保留。
2. 路径长度恰好在边界（等于、差 1、多 1），以及含中文或 emoji 的长路径。
3. 运行现有的快照测试和集成测试，确认短文件名和 `--style=plain` 的输出没有变化。
