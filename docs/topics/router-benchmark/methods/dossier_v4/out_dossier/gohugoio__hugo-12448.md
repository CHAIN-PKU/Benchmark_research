# 仓库档案：hugo 12448（改两个页面后，其中一个页面不重渲染）

以下结论来自静态阅读，没有运行测试。第 2、3、5 节里标"推测"的是我的判断，没有验证过。

## 【1 题面要点】
- 要求的行为：`hugo server` 下同时修改 `content/_index.md` 和 `content/about/index.md` 后，浏览器里正在看的 `/about/` 要刷新。
- 回归范围：v0.122.0 正常，v0.123.0 起失败。
- 复现：给了 `hugo-testing` 仓库的分支和两条 `echo >>` 命令。
- 测试草稿（`TestFoo`）：
  - `Test(t, files, TestOptRunning())`，然后 `b.EditFiles("content/_index.md","home-content|foo","content/p1/index.md","p1-content|bar")`。
  - 编辑后两个断言都失败。issue 作者说"probably doing it wrong"，也就是不确定这是真 bug 还是测试写法问题。
- 没有给修法建议，没有期望的日志或输出，也没有指出出错的位置。

## 【2 相关代码】
- `hugolib/hugo_sites_build.go:694-731`，`handleChange` 闭包，处理 content 组件的变更：
  - 调用 `h.pageTrees.collectAndMarkStaleIdentities(pathInfo)`，并把返回的 ids 追加进 `changes`。
  - 第 704-712 行：fast render 模式下，用 `changes` 里的页面更新 `RecentlyVisited`。
  - 第 714 行：清空 `treeTaxonomyEntries`。
  - 第 716-729 行：处理删除。
- `hugolib/hugo_sites_build.go:880-890`：对 deleted、changedFiles、changedDirs 分别调用 `handleChange`。
- `hugolib/hugo_sites_build.go:898-921`：`whatChanged.Add(changes...)`，然后把去重后的 `changes` 交给 `resolveAndClearStateForIdentities`。
- `hugolib/content_map_page.go:133-177`，`collectAndMarkStaleIdentities`：
  - 在 `treePages` 和 `treeResources` 中按语言维度遍历 key，对节点 `MarkStale`。
  - 回调里用 `nCount` 控制每棵树只取一个 identity 样本。
  - 第 138-153 行的回调只收集第一个节点的 identity，第二个及以后只标记 stale。
- `hugolib/content_map_page.go:1023-1146`，`resolveAndClearStateForIdentities`：
  - 把 stale 的 identity 标记 stale。
  - 清理缓存，收集被驱逐的 identity。
  - 去重 `changes`。
  - 调用 `resolveAndResetDependententPageOutputs`。
- `hugolib/content_map_page.go:1150-1246`，`resolveAndResetDependententPageOutputs`：
  - 所有已渲染页面并行检查。
  - 先用 `p.dependencyManager`（深度 2）匹配 `changes`，再对每个 output 用 `dependencyManagerOutput`（深度 50）匹配。
  - 匹配到就 `resetPo`，把 `renderState` 置 0；结果为 `FinderFoundOneOfMany` 时还会把 `renderOnce` 置 false。
  - 这个 `depsFinder` 在所有 `changes` 和所有页面之间共享。
- `identity/finder.go:77-216`，`Finder.Contains`、`checkOne`：
  - `seenFindOnce` 机制：identity 实现了 `FindFirstManagerIdentityProvider` 时，同一个 `mi.Identity` 只会报告一次 `FinderFoundOneOfMany`。之后的所有匹配都降级为 `FinderFoundOneOfManyRepetition`。
  - 调用方用 `r > FinderFoundOneOfManyRepetition` 判断是否重置，所以被降级的匹配不会触发重置。
  - 推测：这是最可疑的位置。这个"只报告一次"的状态是 Finder 实例级的，在多个变更项之间共享，会让第二个变更项漏掉重置。
- `hugolib/hugo_sites.go:411-457`，`shouldRender`：用 `renderOnce`、`renderState` 和 fast render 的 `RecentlyVisited` 决定是否重新渲染。
- `hugolib/page.go:125-127`：`pageState.ForEeachIdentity` 只返回页面自己。

## 【3 并列与牵连】
- `collectAndMarkStaleIdentities` 对 `treePages` 和 `treeResources` 的处理重复了三遍（`nCount` 重置、回调相同）。如果问题出在"只取一个样本"，三处都要一起检查。
- 第 704-712 行 `RecentlyVisited` 的循环遍历的是整个累积的 `changes`，不只是当前文件产生的 ids，所以会在每次调用时重复添加。
- `identity/finder.go` 的 `Finder` 被多处使用，改 `seenFindOnce` 的语义会影响：
  - 页面 output 重置（`content_map_page.go:1156` 的共享 `depsFinder`）。
  - `dynacache` 的 `ClearOnRebuild`（推测，我没有读那一段）。
  - `identity` 包自己的测试。
- `contentNodeIs.MarkStale`（`content_map_page.go:660`）和 `resourceSources.MarkStale`（`content_map.go:112`）负责各语言节点的 stale 标记。
- `commands/server.go:848` 在 `PartialReRender: true` 下调用，`commands/hugobuilder.go:1007` 是另一个 Build 入口。issue 的复现走 server 的快速渲染路径。

## 【4 现有测试与约定】
- `hugolib/rebuild_test.go` 有大量 `TestRunning(t, files)` 形式的增量重建测试。
  - 第 276 行是带 `RecentlyVisited` 的 fast render 用例。
  - 第 133 行是同时用 Watching 和 Running 跑的 `testRebuildBothWatchingAndRunning`。
  - 我没有读具体断言，不能引用原文。
- `hugolib/integrationtest_builder.go:42` 的 `TestOptRunning` 只设置 `c.Running = true`。
- 约定：`FinderFoundOneOfMany` 的含义来自 `finder.go:174` 的注释"Don't cache this one"，以及 `resetPo` 里"Will force a re-render even in fast render mode"。这是为了避免一个大集合依赖导致整站重渲染。
- 与题面期望是否冲突：没发现冲突。题面期望本来就是 v0.122 的旧行为，所以隐藏测试应该就是题面里的 `TestFoo` 加上对 `public/index.html` 和 `public/p1/index.html` 的断言。
- 注意：issue 作者说"两个断言都失败"。home 页（`_index.md` 编辑）失败可能意味着 `EditFiles`、`Running` 这条测试路径本身还有问题，不只是 `about` 页面。这点需要先验证。

## 【5 边界与隐含要求】
- 多语言：`collectAndMarkStaleIdentities` 的"每棵树只取一个样本"要在多语言站点下仍然正确，不能让一个语言的样本屏蔽另一个语言。
- 同时改多个文件，包括：
  - 两个页面。
  - 一个页面加一个模板。
  - 同一批里既有修改又有新增或删除（`addedContentPaths`，第 860-878 行）。
- fast render 模式（`PartialReRender`）与普通模式要同时成立。issue 的测试没有设置 `RecentlyVisited`，用的是普通路径。
- 不能退化成"每次都全站重渲染"。仓库专门设计了 `OneOfMany` 来避免这一点，修复要保留该行为。
- `_index.md` 与它的子页面存在依赖（列表页依赖子页面，子页面通常不依赖父页面），所以"改父页面会让子页面失效"这个因果方向要看清楚。
- 并发：`resolveAndResetDependententPageOutputs` 是并行的，共享状态的修复必须线程安全。

## 【6 改动规模】
- 预估 1 到 3 个文件，几处改动，属于局部修补，不需要新增结构。
- 很可能落在 `identity/finder.go` 的 `seenFindOnce` 逻辑，或 `content_map_page.go` 的收集与重置逻辑。
- 另外要加一个回归测试，放在 `hugolib/rebuild_test.go`。

## 【7 难点一句话】
难在定位：症状只在"同时改两个有关联的页面"时出现，改动点很可能是一个被多个变更项和页面共享的"只报告一次"去重状态，不在直观的文件监听或标记 stale 的代码里；还要在不丢掉避免过度重渲染这一设计意图的前提下修好它。