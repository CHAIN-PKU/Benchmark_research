**档案：Parent .Pages 在相邻同前缀 section 下错误（getPagesInSection 非递归遍历）**

我共做了 5 次搜索/阅读，没有到 10 次。未查现有测试，也未查 `page__tree.go`、`page.go` 各调用点的具体实参。第 4 节因此基本空白，第 3 节的覆盖也不完整。

**【1 题面要点】**
- 期望行为：首页和 section 页的 `.Pages` 只含直接子页面和直接子 section，不含子 section 内的普通页面。
- 触发条件：相邻目录名互为前缀，且用 `-` 连接（`s1` 与 `s1-foo`）。改成 `s1foo` 后问题消失。
- 版本：v0.123.0 起出现，v0.122.0 正常。
- 复现：给出完整的 Go 测试（`hugolib.Test`，含 `layouts/_default/list.html`）和一个 git 仓库。
- 期望输出：`__|s1|s1-foo|__`。实际输出：`__|p1|s1|s1-foo|__`；在 issue 的测试里是 `__|p1|p2|s1|s1-foo|__`。
- 作者说不清为何测试里多了 p2，原因是该测试把 `content/s1/p2.md` 放在 `s1-foo/_index.md` 之后。
- 题面没有给修法建议。

**【2 相关代码】**
- 最可能要改的是 `hugolib/content_map_page.go:332` 的 `pageMap.getPagesInSection`。
  - 它负责 `.Pages`、`.RegularPages` 等按 section 取页面，结果带缓存，缓存键见 `content_map_page.go:252`。
  - 非递归模式在 `content_map_page.go:359-372` 用一个字符串 `otherBranch` 记录“上一个遇到的分支前缀”，再用 `strings.HasPrefix(key, otherBranch)` 跳过子分支下的节点。
- 底层遍历是 `hugolib/doctree/nodeshifttree.go:333` 的 `NodeShiftTreeWalker.Walk`。
  - 它已经有 `SkipPrefix`（`nodeshifttree.go:319`）和 `ShouldSkip`（`nodeshifttree.go:324`）。
  - 但 `SkipPrefix` 只存在于 walker 内部，`Handle` 回调里可以通过 walker 变量调用它。
  - 同类用法见 `content_map_page.go:493` 的 `rw.SkipPrefix(ownerKey + "/")`。

**【3 并列与牵连】**
- 根因是树按键字典序遍历。基数树里 `-`（0x2D）排在 `/`（0x2F）前面，所以键序为：
  - `/s1`
  - `/s1-foo`
  - `/s1-foo/p2`
  - `/s1/p1`
- 遍历到 `/s1` 时 `otherBranch="/s1/"`。遇到 `/s1-foo` 后被覆盖成 `"/s1-foo/"`，随后的 `/s1/p1` 不再被跳过。
- 这说明 `otherBranch` 只记一个值，是单变量状态的缺陷。修法大概是把每个分支前缀都记入 `SkipPrefix`，或保存全部分支前缀。
- 调用点（都经过同一函数，修一处即可覆盖）：
  - `page.go:233`、`255`、`280`、`298`（Pages、RegularPages、Sections 等）
  - `site_new.go:514`、`530`
  - `site.go:169`
- 其他用到分支判断的地方是 `page__tree.go:69`、`84`、`158` 和 `content_map_page.go:988`、`1309`、`1342`，用途不同，可能不受影响。
- 相似模式：`content_map_page.go:185` 的 `collectIdentitiesSurroundingIn` 用层级计数而非前缀，看起来不受此 bug 影响，但我没有验证。
- `forEachResourceInPage`（`content_map_page.go:490-493`）用 `LongestPrefixAll` 判断归属，思路正确，可作参考。

**【4 现有测试与约定】**
- 我没有读现有测试。issue 里的测试是新增用例，期望 `__|s1|s1-foo|__`，与 v0.122.0 行为一致。
- 题面期望与代码意图不冲突，没有查到外部规范。

**【5 边界与隐含要求】**
- 页面 bundle 本身：叶子 bundle 不是分支，不应记入跳过前缀。
- 多语言、多维度树（`NodeShiftTree` 的 dimension shift）下，同一键可能有多个节点，跳过逻辑要兼容。
- `Recursive` 分支（`content_map_page.go:352`）不受影响，因为它不做跳过。
- `s1-foo` 是 `/s1` 的兄弟而不是子节点，前缀判断必须带尾部 `/`（现有代码已带）。
- 多层嵌套：`s1/a`、`s1/a-b` 这类嵌套同名前缀同样会触发，修复不能只针对顶层。
- 隐藏测试大概率就是 issue 中的测试，也可能加首页、section 页和嵌套情形。

**【6 改动规模】**
- 约 1 个文件、10 行以内的局部修补，位于 `getPagesInSection` 的 `Handle` 回调。
- 需要在 `Handle` 里引用 walker 自己才能用 `SkipPrefix`，或改用前缀切片。
- 不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
定位不难：问题在“单变量 `otherBranch` + 字典序 `-` 排在 `/` 前面”。真正的难点在于修的时候不要破坏多语言或 bundle 的现有行为，修法本身很小。