**档案：PuppetDB SD 数字参数未转为 label**

**【1 题面要点】**
- 期望行为：`include_parameters: true` 时，所有参数都转成 `__meta_puppetdb_parameter_<name>`。题面举例是 `"port": 25`，应得到 `__meta_puppetdb_parameter_port="25"`。
- 实际行为：非字符串、非布尔的参数被丢弃。题面原话："Any parameters that are not strings or booleans are ignored"。
- 题面给了 JSON 输入和期望的 label 输出，也给了 prometheus 配置。
- 题面指出 `resources.go` 里"没有 `int` 或 `float` 的 case"，但没有给修法建议。

**【2 相关代码】**
- `discovery/puppetdb/resources.go:39-83`，`Parameters.toLabels()`，负责把参数 map 转成 `model.LabelSet`。
  - 顶层 switch 在第 44-75 行，处理 string、bool、`[]string`、`[]interface{}`、`map[string]interface{}`。
  - 第 73 行 `default: continue` 会丢弃数字。
  - `[]interface{}` 分支的内层 switch 在第 57-65 行，只处理 string、bool、`[]string`。
  - 第 76 行：`labelValue == ""` 时跳过。
- `discovery/puppetdb/puppetdb.go:207-211`：`json.Unmarshal(b, &resources)`，没有使用 `UseNumber`。因此 JSON 数字会变成 `float64`。
- `puppetdb.go:242-246` 调用 `toLabels()`，并加上前缀 `pdbLabelParameter`（第 53 行）。

**【3 并列与牵连】**
- 并列实现：`toLabels` 内部有两处类型 switch，顶层和数组内层。数字要在两处都加，否则 `[1,2]` 这类数组里的数字元素会得到空字符串。
- 内层数组 switch 没有 default，也没有处理 `map` 和嵌套 `[]interface{}`。这些元素会变成 `""`。
- 嵌套 map 通过递归调用 `toLabels` 处理，所以顶层修好后，map 里的数字会自动生效。
- 唯一的调用点是 `puppetdb.go:243`。
- 文档 `docs/configuration/configuration.md:1180` 只写了"the parameters of the resource"，不一定需要改。

**【4 现有测试与约定】**
- `puppetdb_test.go:110-154`，`TestPuppetDBRefreshWithParameters`，用 `require.Equal` 比较完整的 label 集合。
  - 断言例子：第 138 行 `parameter_access_log` 为 `"true"`。
  - 第 143 行 `parameter_options` 为 `"Indexes,FollowSymLinks,MultiViews"`。
- 测试读取 `fixtures/vhosts.json`。该 fixture 里目前没有数字参数。
- 隐藏测试很可能会往 fixture 里加数字参数，并更新这里的期望 label。
- 因此 fixture 与测试是一起改的，必须与隐藏测试的期望完全一致。
- 现有约定：空字符串和空数组不产生 label，所以 `directoryindex: ""` 和 `additional_includes: []` 都没有 label。这与题面不冲突。
- 没有外部规范。

**【5 边界与隐含要求】**
- 数字格式化：`float64` 要用 `strconv.FormatFloat(value, 'g', -1, 64)`，使 `25` 显示为 `"25"` 而不是 `"25.000000"`。
- 大整数会有科学计数法的问题。`'g'` 对 ≥1e21 才切换成指数形式，但对较大的数字（如 `1e6` 之后）可能会输出 `1e+06`。更稳妥的做法是 `'f'` 或 `UseNumber`。
- 还要考虑：
  - 数组里的数字元素，见【3】。
  - `0` 和 `0.0` 不能被"空值跳过"逻辑误丢，因为判断的是字符串是否为空，所以 `"0"` 是安全的。
  - 负数。
  - `nil` 值（JSON null）仍应被跳过。
- 如果改成 `UseNumber`，类型会变成 `json.Number`，要新增 case，且 `Parameters` 的其他使用者可能受影响。

**【6 改动规模】**
- 最小修补：只改 `resources.go`，在两个 switch 里各加一个 `float64` case，约 2-6 行。
- 另外要更新 `fixtures/vhosts.json` 和 `puppetdb_test.go`。
- 属于局部修补，不需要新增结构。

**【7 难点一句话】**
逻辑本身简单，难点在数字格式化的细节（整数不带小数点、大数不用科学计数法），以及别漏掉数组内层那个 switch。