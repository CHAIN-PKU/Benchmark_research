# 仓库档案：stale 时间戳字段白名单漏掉 spec 声明的日期字段

## 【1 题面要点】
- **要求的行为**：生成的 `pm_stale.go` 用于判断不活跃的时间戳字段集合，应改为「硬编码白名单 ∪ spec 里声明为 `format: date-time` 的属性名（限于被同步的资源）」。
- **复现**：`trello-pp-cli stale --days 14` 返回空，而 `health` 在同一份镜像数据上统计出 93 条 stale。Trello 的字段是 `dateLastActivity`，不在白名单里。
- **关键句**：
  - "Build the stale timestamp-field set as `hardcoded allowlist ∪ spec-declared date-time property names for the synced resources`."
  - "Guard: union is additive only — never removes existing allowlist entries."
- **测试描述**：
  - 正向：spec 里有 `dateLastActivity`（date-time）的 card 属性时，生成的 `stale` 能找到早于 N 天的行。
  - 反向：用 `updated_at` 的 API 行为不变。
- **接口**：题面写明「No new interfaces」。没有给函数名、签名或具体实现方式。

## 【2 相关代码】
- `internal/generator/templates/workflows/pm_stale.go.tmpl`
  - 第 24-36 行：`var staleTimestampFields = []string{...}`，11 个硬编码键。
  - 第 60-74 行：`buildStaleTimestampPredicate()` 遍历该切片，为每个字段生成两个占位符的 SQL。字符串用 `typeof='text' AND < cutoffStr`，数值用 `typeof IN (integer, real) AND < cutoffEpoch`。ORDER BY 用 COALESCE。
  - 第 116-121 行：绑定 `n*2` 个参数。
  - 第 181 行：Go 侧扫描循环同样遍历 `staleTimestampFields`，第一个命中的键生效。
  - WHERE、ORDER BY、Go 扫描三处共用同一个切片。因此只要切片里加入动态字段，三处会自动同步。
- `internal/generator/generator.go:2695-2698`
  - 渲染 workflow 模板时调用 `g.renderTemplate(tmpl, outPath, g.Spec)`，传入的 data 是 `*spec.APISpec`。
  - 模板能拿到 `.Resources` 和 `.Types`，但没有现成的 stale 字段列表。
  - 模板函数表在 `generator.go:221-522` 附近。已有的辅助函数如 `hasNonScalarType(types)` 接收 `map[string]spec.TypeDef`，可作为新增函数的参照。
- `internal/spec/spec.go:1683-1692`
  - `TypeField{Name, Type, Format}`，注释说明 `Format` 来自 OpenAPI 的 format。
  - `TypeDef.Fields` 是类型字段列表。
- `internal/generator/schema_builder.go:257-298`
  - `collectResponseFields(s, r)` 从 `ep.Response.Item` 对应的 `s.Types` 取字段，GET 优先，没有 GET 才用非 GET。
  - 这是「某个资源的响应字段」的现成取法，可复用。
  - `schema_builder.go:312-327`：`sqliteType` 把 `date-time` 和 `date` 都映射为 `DATETIME`。
- `internal/openapi/parser.go:3741`：已有 `p.Format == "date" || "date-time"` 的判断。需确认解析器是否把 `Format` 写入 `TypeField`（`parser_test.go:698` 的断言说明会写入）。
- `internal/generator/generator.go:1897,3184`：workflow 模板的注册与构造器映射，改动无需涉及。

## 【3 并列与牵连】
- 同类 workflow 模板：`pm_orphans.go.tmpl`、`pm_load.go.tmpl`。它们不用时间戳白名单，题面只涉及 stale。
- 题面提到手写的 `health`（Trello 里读 `dateLastActivity`）。`insights/health_score.go.tmpl` 是另一个模板，与本题无关。
- `comm_health.go.tmpl` 属于 communication 原型，也不涉及。
- stale 模板只在 `project-management` 原型下启用（`vision_templates.go:134-139`）。Trello 是否走这条路径要看规划，但测试可以直接设置 `gen.VisionSet.Workflows`（见 `generator_test.go:12820-12828` 的写法）。
- 受影响面：所有生成了 `pm_stale.go` 的 CLI。因为是纯加法，已有 API 的输出只会多出若干字段，不会少。
- `internal/pipeline/scorecard.go:652` 只检查 `pm_stale.go` 里有没有 `"limit"`，不受影响。

## 【4 现有测试与约定】
- `generator_test.go:13040-13085` 的 `TestStaleTemplateCoversCommonTimestampFields` 直接读模板源文件做字符串断言：
  - 第 13059：`assert.Contains(t, body, `"`+field+`"`)`，对 11 个字段逐个检查模板里有 `"field"` 字面量。
  - 第 13067：`Contains(body, "buildStaleTimestampPredicate()")`。
  - 第 13074：`Contains(body, `"COALESCE(" + strings.Join(coalesceArgs, ", ") + ") ASC"`)`，**逐字符断言这一行字符串**。
  - 第 13081：`Contains(body, "typeof(")`。
  - 第 13083：`Contains(body, "cutoffEpoch")`。
- 这些断言约束模板源文本。重构时必须保留这些字面量，包括 11 个带引号的字段名和 COALESCE 那一行写法，否则旧测试会失败。
- `generator_test.go:12814-12838`、`12840-12889` 渲染完整 CLI，检查 `pm_stale.go` 的 annotation 和 `maybeEmitSyncHints`。使用 `minimalSpec("pmworkflows")`，所以新代码对没有 Types 的最小 spec 必须不出错。
- 约定：
  - 模板里 `{{...}}` 渲染后会过 `go/format`，所以语法必须合法。
  - 渲染失败只会打印 warning 并跳过（`generator.go:2699`），错误容易被吞。
  - 白名单顺序有意义（第一个命中的键生效），新增字段应追加在末尾，不改变已有顺序。
- 与题面不冲突：题面要求只增不减，旧测试也要求保留白名单。
- 隐藏测试很可能是：
  - 生成 CLI 后读 `pm_stale.go`，断言含 `"dateLastActivity"`。
  - 反向断言 `updated_at` 的 spec 不多出无关字段，或字段集没变化。
  - 也可能直接测一个新的 Go 辅助函数（题面说无新接口，名字无法预知）。

## 【5 边界与隐含要求】
- **去重**：spec 里声明了 `updated_at` 且 format 为 date-time 时，不应在切片里重复，否则 SQL 会多出重复子句。
- **"synced resources" 的范围**：只取被同步资源的响应类型字段，不是全部 `Types`。需要决定如何确定「可同步资源」。`internal/profiler/profiler.go` 的 `SyncableResource` 是一个线索，但它在另一个包。
- **创建类字段**：`created_at`、`createdAt`、`dateCreated` 同样是 `date-time`。若全部并入，stale 会把「创建时间早于 N 天」的行也当作 stale，且 COALESCE 顺序可能先取到 created 字段，语义出错。因此可能需要过滤掉含 create 的名字，或把动态字段排在白名单之后。题面没有给规则，这是最大的语义风险。
- **日期格式**：`format: date` 是否也算。`sqliteType` 把它和 date-time 同样处理。题面只写 date-time。
- **Trello 实际值格式**：`dateLastActivity` 是 RFC 3339 字符串，现有字符串比较可以处理。
- **字段名安全**：字段名会拼进 `json_extract(data, '$.%s')` 的 SQL，含特殊字符（引号、点、空格）需要转义或过滤。Go 字面量也需要 `goLiteral` 一类的转义。
- **确定性输出**：Types 是 map，遍历顺序随机，必须排序，否则生成结果不稳定。
- **嵌套属性**：只取顶层属性。
- **空 spec**：没有任何 Types 时，输出应与现在完全一致。
- **Go 侧扫描**：第 181 行的循环自动覆盖新字段。但 `UpdatedAt` 展示和 `daysSince` 的计算都依赖第一个命中的键，字段排序会影响显示。

## 【6 改动规模】
- 预计改 2-3 个文件，约 3-5 处：
  1. 在 `spec` 或 `generator` 里新增一个函数（或方法）收集日期字段，并注册为模板函数（`generator.go` 函数表）。
  2. `pm_stale.go.tmpl` 里把切片改成「硬编码 + 模板渲染出的额外项」，同时保留旧测试要求的字面量。
  3. 新增测试：渲染一个带 `dateLastActivity` 的 spec，断言输出，另有反向用例。
- 属于局部修补，不涉及多层贯穿，也没有新结构。

## 【7 难点一句话】
难点在于设计「哪些 date-time 字段算活动时间戳」：既要把 `dateLastActivity` 加进去，又要避开 `created_at` 这类会让 stale 语义出错的字段。同时要保证确定性排序、去重，并保留旧测试对模板源文本的逐字断言。题面没给规则，隐藏测试的断言形式也无法从题面推出。