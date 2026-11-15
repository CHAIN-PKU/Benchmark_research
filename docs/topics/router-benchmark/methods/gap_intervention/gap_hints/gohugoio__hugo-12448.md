## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
- `identity/finder.go` 的 `Finder.checkOne`、`seenFindOnce` 和 `FinderFoundOneOfMany` / `FinderFoundOneOfManyRepetition`。
  - `FindFirstManagerIdentityProvider` 这条分支会把「第一个管理器身份」记入 `seenFindOnce`，之后同一身份再命中就返回 Repetition。
  - 一次重建里有多个变更（这里是 `_index.md` 和 `about/index.md`）时，先命中的变更可能让后一个页面被当成重复而漏掉重置。
  - 请查清这个「只命中一次」的记录是按什么粒度去重的，以及它和「多个变更并发查同一批页面」的关系。
- `hugolib/content_map_page.go` 的 `resolveAndResetDependententPageOutputs`。
  - 这里有两步判断：先用 `depsFinder.Contains(..., p.dependencyManager, 2)` 查页面级，再用 `po.dependencyManagerOutput, 50` 逐输出格式查。
  - 判断条件是 `r > FinderFoundOneOfManyRepetition`。
  - `depsFinder` 在所有页面、所有变更之间共享，并由 `rungroup` 并行使用，所以要查它的状态会不会在页面之间互相污染。
  - `resetPo` 在 `r == FinderFoundOneOfMany` 时才把 `renderOnce` 置 false。请确认这个分支和 `renderState` 重置的关系。
- `hugolib/hugo_sites.go` 的 `BuildCfg.shouldRender` 和 `hugolib/page__output.go` 的 `renderOnce`。
  - 它们决定页面在 fast render mode 下是否重渲染，所以要一并核对。
  - 修复后，这两个页面都要被判为需要渲染。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
- 一次编辑里同时改多个页面，顺序要不同：先改 section/home 再改叶子页，以及反过来。结果不应依赖顺序。
- 被改的页面彼此有依赖关系。例如首页是列表页，列出了子页面，所以首页的变更可能把依赖它的页面也带出来。
- fast render mode 开和关两种情况都要看。题面里 `hugo server` 默认是 fast render。
- 多输出格式或多语言站点下，每个输出格式的 `pageOutput` 是否都被重置。

**C. 仓库里已有的约定、文档或测试中需要核对的地方**
- `identity/` 目录下 finder 的现有测试，以及 `hugolib` 里与 rebuild、`TestOptRunning`、`EditFiles` 相关的测试（例如 `rebuild_test.go`）。
  - 改动前后它们的期望都要保持，尤其是「只命中一次」所对应的计数断言，例如 `testCounters`。
- `FinderFoundOneOfMany` 的结果「不缓存」，见 `checkManager` 里的注释。请遵守这个约定，不要让新逻辑把这类结果写进 `answers`。
- 题面里的集成测试写法（`hugolib.Test` 加 `TestOptRunning`）。可以照这个结构补一个回归测试，但要自己确认断言本身是对的：题面说两个最终断言都失败，可能有一部分是测试写法的问题。

**D. 建议提交前额外自测的情况**
1. 题面的场景：同时编辑 `content/_index.md` 和 `content/p1/index.md`，然后断言两个输出文件都更新。
2. 调换两个编辑的顺序，并分别多跑几次（并行执行可能有竞态）。
3. 只编辑一个页面，确认其他页面没有被多余地重渲染（核对渲染计数），同时跑一遍 `identity` 和 `hugolib` 里现有的 rebuild 测试。
