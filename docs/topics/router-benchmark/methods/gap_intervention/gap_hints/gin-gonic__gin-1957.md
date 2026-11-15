## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) binding/binding.go 导出变量块需注册 binding.Header（对照 Query/Uri）；2) context.go 里成对的 BindHeader/ShouldBindHeader（对照 BindQuery/ShouldBindQuery、BindUri/ShouldBindUri）；3) binding/form_mapping.go 的 mapForm/mapUri 是按 tag 区分的薄封装，底层 mapFormByTag，header 需用 header tag，查看 mapping/tryToSetValue 的 tag 传递。
B. 1) req.Header 键名已规范化而 formSource 精确查 map，注意 tag 大小写/连字符（如 header:"user-agent"）能否取到；2) 无 tag 字段默认用字段名，header 场景是否合理；3) 缺失头应保持零值不报错，非 string（int）解析失败要报错；4) 绑定后需调用 validate（如 required、slice 多值头）。
C. 1) binding/query.go、uri.go 是模板（Name/Bind 签名/validate）；2) binding_test.go 的 TestUriBinding 与 Query 测试、form_mapping_test.go 测 mapUri 的用例可仿照；3) README 绑定章节（Methods 列表约 624-627 行、Only Bind Query String、Bind Uri）需同步文档。
D. 1) httptest 带 Rate/Domain 头调用 ShouldBindHeader，确认 int 与 string 都被填充；2) 头键名大小写不一致或 tag 与规范化头名不一致（如 header:"x-request-id"）能否取到；3) 缺头、非法 int（Rate: abc）、BindHeader 出错返回 400，并确认现有 query/form/uri 测试仍通过。
