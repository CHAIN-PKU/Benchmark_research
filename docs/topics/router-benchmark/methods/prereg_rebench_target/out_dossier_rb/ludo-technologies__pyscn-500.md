**pyscn 分号空语句误报：仓库档案**

**【1 题面要点】**
- 要求的行为：`return`/`raise` 后面带尾随 `;` 时，`;` 这个空语句不应产出 dead-code 的 `unreachable_branch` warning。
- 复现：题面给了两个函数 `f`、`g`，运行 `pyscn analyze --json --no-open semi_repro.py`。
- 实际输出：`"code": ";"`、`"reason": "unreachable_branch"`、`"severity": "warning"`，列号 `0-0`。
- 期望输出的关键句："Empty statements (the no-op produced by a trailing `;`) should be filtered out before emitting dead-code findings"。题面还说"At most this is a low-severity style hint"，但这只是"至多"，不是要求。
- 修法建议："Skip CFG nodes that correspond to empty statements (Python `pass`-equivalent / bare `;` separators) when collecting unreachable-branch findings in the dead-code analyzer."
- 没有新增接口。隐藏测试大概率构造带 `;` 的源码，断言没有 finding；也可能断言 CFG 或块里没有 `;` 节点。

**【2 相关代码】**（均为阅读后的判断，没有运行复现）
- `internal/parser/ast_builder.go:61-206`，`buildNode`。
  - tree-sitter 的匿名 `;` token（`Type()==";"`）没有匹配任何 case，落到 `default:`（191-205）。
  - 这里会生成一个 `NodeType(";")` 的通用节点。
  - `code=";"` 就是这么来的：`getNodeDescription` 的 `default` 返回 `string(node.Type)`（`internal/analyzer/dead_code.go:459-460`）。
  - 通用节点的 `Location` 来自 `getLocation`。0-0 列的成因我没有核实。
- `internal/parser/ast_builder.go:1677-1692`，`buildBlock`。
  - 它遍历所有子节点，只跳过 `isTrivia`。`isTrivia`（2074-2077）只认 `comment` 和 `line_continuation`。
  - 所以块内的 `;` 子节点被加进 `Body`。
  - 第 217、793 行也有类似的子节点遍历，`buildModule` 可能同样会带入 `;`，需要核对。
- `internal/analyzer/cfg_builder.go:275`，`processStatement`。
  - `return` 分支（317-361）添加语句后新建 `LabelUnreachable` 块。
  - 476-479 的 `default:` 把任何未知节点（包括 `;`）加入当前块。
  - 所以 `;` 落进这个不可达块，该块非空，`GetUnreachableBlocksWithStatements` 就会返回它（`reachability.go:140-150`）。
  - `raise` 的处理在同文件，我没有读到，应当同理。
- `internal/analyzer/dead_code.go:109-150`，`Detect`。它遍历不可达块。
- `internal/analyzer/dead_code.go:190-217`，`analyzeDeadBlock`。
  - 只在块为空时返回。
  - 默认 reason 是 `ReasonUnreachableBranch`、severity 是 warning（220-232）。
  - 只有 `findTerminatorInPredecessors` 找到前驱的终结语句才会改成 `unreachable_after_*`。
- `dead_code.go:412-425`，`getBlockCode`。拼接各语句的描述。
- `dead_code.go:396-409`，`getBlockStartLine` 和 `getBlockEndLine`。取首尾语句的 Location。
- `service/dead_code_service.go:299-320`，`convertToFunctionDeadCode`。把 analyzer 的 finding 转成 domain 的 finding，`Code` 直接透传。

**【3 并列与牵连】**
- 有三个可选的修复层，选哪个会影响牵连面。
  - 在 `buildBlock` 或 `buildModule` 里丢弃 `;` 节点。
    - 这个修法最彻底，所有分析器（复杂度、克隆 APTED、嵌套深度）都不再看到 `;`。
    - 但会改变 AST 的形状。
    - 克隆检测的树结构里目前可能带有 `;` 节点，改了会让带分号的代码的相似度略有变化。
  - 在 `cfg_builder.processStatement` 里对 `;` 提前 return。
    - 这是 CFG 层的局部修法，只影响 CFG 和 dead code。
    - 但其他以 CFG 为输入的分析仍可能看到 `;` 的某些痕迹，我没有查。
  - 在 `Detect` 或 `analyzeDeadBlock` 里过滤。
    - 这个修法最局部。
    - 但要处理"块里既有 `;` 又有真代码"的情况，否则 `Statements` 全是 `;` 的块虽然被跳过，混合块仍会带 `;`。
- 其他调用点：
  - `analyzeDeadBlock` 是唯一生成 finding 的地方。
  - `DetectInFile` 在 181 行用 `result.DeadBlocks > 0` 决定是否保留结果。
  - `Detect` 在 136 行用 `len(unreachableWithStatements)` 设置 `DeadBlocks`。
  - 如果只在 `analyzeDeadBlock` 里过滤，`DeadBlocks` 仍会计入这个块，导致 `DeadBlocks>0` 但没有 finding 的不一致。
  - 这个计数还会进入 `GetDeadCodeRatio`，以及 `service/dead_code_service.go:273-282` 的 `deadCodeRatio`。
  - 所以过滤最好发生在计数之前，也就是在块级别或更早处理。
- 并列实现：`parser/visitor.go:392` 有一处 `stmt.Type != NodePass` 的判断，我没有读上下文。它可能是"函数体是否只有 pass"之类的逻辑，值得看看分号是否影响它。
- 结构相近的 `NodePass` 处理出现在 `cfg_builder.go:363` 和 `dead_code.go:457`。

**【4 现有测试与约定】**
- `internal/analyzer/dead_code_test.go` 里有这些测试：
  - `TestDeadCodeDetection`（14 行起）
  - `TestDeadCodeWithStatements`（348 行起）
  - `TestDeadCodeInExceptionHandling`（392 行起）
  - `TestDeadCodeEdgeCases`（505 行起）
  - `TestDeadCodeMetrics`（623 行起）
- 它们用的是 `HasUnreachableCode()` 等布尔断言和 findings 计数。我只扫了部分行，没有逐条读断言。
- `service/dead_code_service_test.go` 和 `app/dead_code_usecase_test.go` 是上层测试。
- 仓库里没有找到专门处理 `;` 的约定。仓库约定是用 tree-sitter 解析，`isTrivia` 是现成的过滤钩子。
- 与题面期望不冲突。`docs/algorithms/dead-code.md` 我没有读，可能描述了预期行为。

**【5 边界与隐含要求】**
- 题面隐含：`return x;` 之后，`g` 函数不应有任何 finding。
- 真正的死代码仍要报：`return x; y = 1` 里的 `y = 1` 应当仍被报告（`unreachable_after_return`）。
- `return x;;`（连续多个分号）和 `return x; ;`。
- `;` 在同一行分隔的多个语句，如 `a = 1; b = 2`。分号本身不是语句，但相邻语句不能丢。
- 混合块：`return x; ; y = 1`，应当只报 `y = 1`，且 `Code` 里不应出现 `;`。
- 模块级、类体、`if`/`for`/`while` 内的 `;`，也就是不止函数体。
- 嵌套函数和类里的 `;`。
- `;` 会不会影响 `pass`、`break`、`continue` 之后的情形。
- 是否需要新增一个低级别 "info" 提示：题面说"at most"，不是必须。
- 行号和列号：过滤后不应让起止行出现 0 或负值。

**【6 改动规模】**
- 最小修补：1 个文件、1 到 2 处（`buildBlock` 加一个类型判断，或 `processStatement` 加一个 case），再加一个测试。
- 要同时覆盖 `buildModule` 和 `buildBlock` 就是 1 个文件、2 到 3 处。
- 这是局部修补，不需要新增结构或贯穿多层。

**【7 难点一句话】**
难点在于选对过滤层：必须在计数（`DeadBlocks`）之前、又不改变其他分析器的 AST 输入的前提下丢掉 `;` 节点，同时保证 `return x; y = 1` 里的真死代码仍被报告。

**未核实的点**：`;` 在 `getLocation` 里为何得到 0-0 列、`raise` 的 CFG 分支、`buildModule`（217 行）是否也带入 `;`、`visitor.go:392` 的上下文，以及现有测试的具体断言。