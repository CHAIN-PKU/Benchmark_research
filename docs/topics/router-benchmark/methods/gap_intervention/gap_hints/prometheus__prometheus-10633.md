## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) resources.go 的 toLabels 有外层和 []interface{} 内层两处 switch，数组内的数值元素也要处理，否则变成空串元素。2) JSON 解码后数字的 Go 类型要先查清，再决定覆盖哪些 case。3) map 分支是递归的，嵌套对象里的数值也要验证。
B. 1) 整数和浮点数（0.5、1e6、大整数）的输出格式，整数不应带小数或科学计数法。2) 数值 0 不能被 labelValue=="" 的跳过逻辑误丢。3) 数组中混合类型和 null 的处理。4) 数组里不支持元素的现有处理应保持不变。
C. 1) puppetdb_test.go 的 TestPuppetDBRefreshWithParameters 和 fixtures/vhosts.json 的现有期望不能变，空数组、空串、空对象仍然跳过。2) 布尔值用 strconv.FormatBool，数值转换要风格一致；数组值用 separator 的约定要核对。3) docs/configuration/configuration.md 约 1173 行的 puppetdb 标签文档看是否需要同步。
D. 1) 在 fixture 里加整数、浮点数、0，核对标签值。2) 数组里放数值或混合类型，核对拼接结果。3) 嵌套对象里放数值，核对前缀和值，并跑完整 puppetdb 包测试。
