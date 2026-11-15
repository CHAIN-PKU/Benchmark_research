## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) hugolib/content_map_page.go 的 pageReverseIndex initFn 只收录 p.File()!=nil 的页面,键为 PathInfo().BaseNameNoIdentifier();适配器页面无 File,很可能因此查不到;查适配器页面的 PathInfo 来源。2) pagecollections.go getContentNodeForRef 的 doSimpleLookup / ambiguousContentNode / nameNoIdentifier 逻辑。3) 索引的 Reset / sync.Once 与增量重建后适配器页面是否被重新收录。
B. 1) 文件页与适配器页同名应走 ambiguous 报错路径。2) 不同章节的两个适配器页同名。3) 适配器生成 bundle / _index / 带语言标识符的页面时键是否仍为不含标识符的名称。4) path 带或不带前导斜杠、GetPage 参数带或不带 .md。
C. 1) 文件页的键规则 BaseNameNoIdentifier,适配器页应与之一致。2) 参考 hugolib 里 GetPage 测试和内容适配器测试的写法。3) Ref/RelRef(isReflink)路径也走同一索引,确认能解析且无回归。
D. 1) 题面完整测试再加 ref/relref 变体。2) 文件页与适配器页同名的歧义行为,对照现有测试。3) 跑现有 GetPage、内容适配器、多语言测试确认无回归。
