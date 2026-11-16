# 仓库档案：InferEndpointTemplateVarsFromBaseURLs

做法是在 `internal/spec/spec.go` 加一个方法，并在 `Generator.New` 里调用。我只读了代码，没有跑测试。

## 1 题面要点
- **要求的行为：** 规格的 URL 字段里只要含 `{PLACEHOLDER}`，就把占位符名推断进 `EndpointTemplateVars`，让生成的客户端带上 URL 解析器。推断必须发生在校验和生成之前。
- **要扫描的字段：** `BaseURL`、`BasePath`、`GraphQLEndpointPath`、tier 的 `BaseURL`，以及资源、端点、子资源的 `BaseURL`。
- **排序与去重：**
  - "Preserve existing explicit entries and their order, append each newly discovered placeholder once"
  - "use deterministic ordering when traversing maps"
- **调用时机：** "`Generator.New` must invoke placeholder inference before it returns, so callers can observe the inferred `EndpointTemplateVars` immediately"
- **接口：** `InferEndpointTemplateVarsFromBaseURLs()` 无参数、无返回值，是 `*APISpec` 的方法，改的是接收者本身。
- **没有给出：** 复现步骤、期望输出和具体修法。
- **术语问题：** 题面反复说 `resolveBaseURL`。我在整个仓库里搜过，没有这个标识符。现有的 URL 解析器是 `buildURL`，在 `internal/generator/templates/url.go.tmpl`。题面的措辞大概是指"生成 `url.go`/`buildURL`"。

## 2 相关代码
- `internal/spec/spec.go:94-197`（`APISpec`）：
  - 相关字段在 126-144 行：`BaseURL`、`BasePath`、`GraphQLEndpointPath`、`EndpointTemplateVars`。
  - 新方法放在这个文件。
- `spec.go:199-208`：`TierRoutingConfig.Tiers`（map）和 `TierConfig.BaseURL`。
- `spec.go:1309-1322`：`Resource`，含 `BaseURL`、`Endpoints` map、`SubResources` map（递归）。
- `spec.go:1362-1365`：`Endpoint.BaseURL`。
- `spec.go:1333-1360`：`HasResourceBaseURLOverride` 和 `resourceHasBaseURLOverride`。它们是现成的递归遍历范例，但不按排序顺序遍历。
- `internal/generator/generator.go:168-204`：`New`。
  - 开头先做 owner 清洗。
  - 在构造 `Generator` 之前（约 200 行）调用新方法最合适。
- `generator.go:1722`：`if len(g.Spec.EndpointTemplateVars) > 0` 时才渲染 `url.go.tmpl`。这是"是否生成解析器"的唯一开关。
- `internal/generator/templates/client.go.tmpl`：
  - 1060-1122 行：按 `.EndpointTemplateVars` 决定走 `buildURL` 还是裸拼接。
  - 165-178 行：tier 的 `BaseURL` 用 `printf "%q"` 烧进去。
  - 627-638 行：缓存键里混入模板变量。
- `config.go.tmpl`（76、200、216 行）：读取环境变量。
- `url.go.tmpl:18`：正则 `\{([a-zA-Z_][a-zA-Z0-9_]*)\}`。
  - 推断应使用同样的字符集。
  - 占位符名必须与它一致，否则 `buildURL` 替换不上。
- `templates/url.go.tmpl:26-30`、`sync.go.tmpl`、`readme.md.tmpl`：都遍历 `EndpointTemplateVars`。

## 3 并列与牵连
- **并列的字段：** 需要同样处理的字段有 7 类：
  - `BaseURL`、`BasePath`、`GraphQLEndpointPath`
  - tier 的 `BaseURL`
  - 资源的 `BaseURL`
  - 端点的 `BaseURL`
  - 子资源的 `BaseURL`，需要递归
- **map 遍历：** `Tiers`、`Resources`、`Endpoints`、`SubResources` 都是 map，必须排序键后遍历。
- **调用点：**
  - 题面明确要求 `Generator.New` 调用。
  - 另有 `internal/cli/root.go:571` 调用 `gen.Validate()`，那是生成后的质量门，不是规格校验。
  - 规格解析器（openapi、graphql、docspec、crowdsniff、browsersniff）也各自调用 `apiSpec.Validate()`。这些不是必改的，因为题面只要求 `New`。
- **解析器的现有行为：** `internal/openapi/parser.go` 约 538、594、2869-2884 行已经为 server URL 变量填充 `EndpointTemplateVars`，因此显式条目已经存在，推断必须去重。
- **改动的连带影响：**
  - 一旦推断出变量，`url.go`、config 的 `TemplateVars`、sync 的 `--path-context`、README 都会随之生成。
  - 这些都是模板分支，已有实现。
  - 无占位符的规格保持字节不变，现有测试 `TestGenerateNoEndpointTemplateVarsByteCompat` 守着这一点。
  - profiler 的 `IsEndpointTemplateVar`（`profiler.go:791-796`）会受影响。它依赖 `EndpointTemplateVars` 判断路径是否可独立列出，推断后行为可能改变。

## 4 现有测试与约定
- `generator_test.go:11203` 的 `TestGenerateEndpointTemplateVarsRuntimeSubstitution` 使用 `shopifyTemplateVarsTestSpec()`，BaseURL 为 `https://{shop}`，并显式设置 `EndpointTemplateVars`。断言包括：
  - 11217 行 `"func buildURL("`
  - 11239 行 `"buildURL(c.BaseURL, path,"`
  - 11241 行 NotContains 裸拼接
- `generator_test.go:11645` 的 `TestGenerateNoEndpointTemplateVarsByteCompat` 要求无变量时不生成 `url.go`（11659 行）。
- `generator_test.go:11906` 的 `TestGenerateResourceBaseURLWithEndpointTemplateVars` 手动设置 `apiSpec.EndpointTemplateVars = []string{"shop"}`。
- 约定：
  - 变量名和环境变量名由 `DefaultEndpointTemplateEnvName` 决定，见 `spec.go:255`。
  - 命名为 `<API>_<UPPER_PLACEHOLDER>`，经过 `naming.Snake`。
  - `docs/SPEC-EXTENSIONS.md:303-353` 描述了 `EndpointTemplateVars` 的来源。
- 与题面的冲突：
  - 题面写的是大写 `{PLACEHOLDER}`，而 `url.go.tmpl:13-18` 的注释说占位符是"lowercase ASCII identifiers"，正则实际接受大小写。
  - 注释与正则略有出入，但不影响推断。
  - 没有 `resolveBaseURL` 的参考实现。
- 隐藏测试大概率包括：
  - 直接调用 `InferEndpointTemplateVarsFromBaseURLs` 并比较切片。
  - 调用 `New(spec, dir)` 后检查 `spec.EndpointTemplateVars`。
  - 生成后 `go build` 并检查 `url.go`。

## 5 边界与隐含要求
- 显式条目保持原位置和顺序，新条目追加在后；重复的只出现一次，包括同一占位符在多个字段里出现，也包括与显式条目重名。
- 重复调用要幂等，因为 `New` 可能被多次调用，调用方也可能自己再调。
- map 遍历要排序键；同一个字段内按出现顺序提取。
- `s` 为 nil 时要安全返回（现有方法都有 nil 守卫）。
- 子资源要递归，且子资源自己的端点也要扫。
- 不扫端点的 `Path`：路径里的 `{id}` 是路径参数，不是模板变量，否则会误报。
  - 题面只列了 `BaseURL`/`BasePath`/`GraphQLEndpointPath` 等 URL 字段。
  - 但 `GraphQLEndpointPath` 本身含 `{version}`，要扫。
- 占位符正则要和 `url.go.tmpl` 一致；不匹配的花括号（如 `{1}`、嵌套）应忽略。
- tier 的 `BaseURL` 被烧进 `baseURLForRequest`，推断出变量后会走 `buildURL`，这一路径要能编译。
- 同时有 `HasResourceBaseURLOverride` 的规格，模板走 `isAbsoluteURL` 分支，要确认编译正常。
- 推断出的变量没有 `EndpointTemplateVarDefaults`，运行时按未设置处理，这是预期行为。
- "buildable client"：`New` 之后 `Generate()` 渲染 `url.go`，需要 `go build` 通过。

## 6 改动规模
- 约 2 个文件：`spec.go` 新增一个方法加两三个小的辅助函数，`generator.go` 在 `New` 里加一行调用。
- 模板大概率不用改，分支已经基于 `.EndpointTemplateVars` 存在。
- 属于局部补丁，不需要新结构，也不贯穿多层。
- 另外可能补测试。

## 7 难点一句话
代码量小，难点在于覆盖全部 7 类 URL 字段、对 map 做确定性排序、与解析器已填的显式条目去重，并确认在 `New` 里调用后，tier 和资源级 `BaseURL` 的生成结果仍能编译。