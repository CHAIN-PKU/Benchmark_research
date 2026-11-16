正在查证的最后阶段，已读完相关代码和测试，下面直接给出档案。

## 仓库档案：Incremental regeneration 忽略 data 文件变更

**【1 题面要点】**
- 期望行为：单独多次执行 `jekyll build --incremental` 时，修改 `_data/*.yml` 后页面应更新。
- 实际行为：原文是 "`jekyll build --incremental` ignores any and all changes to my home page's data files, it outputs exactly the same web page after each build. Using `jekyll serve -i -l` works, however."
- 复现：只给了外部仓库链接，是 `yarn dev` 加改 `_data/amyspark.yml` 里的日期。仓库里没有最小复现。
- 题面没有给期望输出，也没有给修法建议。

**【2 相关代码】**
- `lib/jekyll/regenerator.rb`：管理增量元数据 `.jekyll-metadata`，记录 mtime 和 deps。
  - `regenerate?`（22）按 Page、Document 和其他三类分发。
  - `regenerate_page?`（165）和 `regenerate_document?`（172）只调用 `source_modified_or_dest_missing?`（76）。
  - `modified?`（84）、`existing_file_modified?`（179）和 `add_dependency`（106）负责依赖检查。
  - 当前只检查"自身文件和 deps 的 mtime"，没有任何 data 文件的概念。
- `lib/jekyll/readers/data_reader.rb:21-68`：`read`、`read_data_to`、`read_data_file` 读取 `_data` 下的 yaml、yml、json、csv、tsv。读取时不向 regenerator 登记任何东西。
- `lib/jekyll/reader.rb:30-39`：`read_data` 先读站点 data，再读主题 data（`in_theme_dir`），最后 `deep_merge_hashes`。
- `lib/jekyll/site.rb`：
  - `process`（74）的顺序是 reset、read、generate、render、cleanup、write。
  - `write`（228-236）里是 `item.write(dest) if regenerator.regenerate?(item)`，之后 `write_metadata`。
  - `reset`（111）会 `clear_cache`。
  - `site_data`（280）是 `config["data"] || data`。
- `lib/jekyll/drops/site_drop.rb`：Liquid 的 `site.data` 通过 `delegate_method_as :site_data, :data` 访问，没有依赖追踪钩子。
- `serve.rb:149` 的 watcher 路径用 `regenerate?`，所以 `serve -l` 能工作。我没有细读它为何能工作，推测是它每轮重新 `process` 并且 data 有变就整站重来，需验证。

**【3 并列与牵连】**
- 现有依赖登记点只有两处：layout（`renderer.rb:200-207`）和 include（`tags/include.rb:133` 与 `247`）。data 需要新增并列的机制。
- `site.data` 不是通过 tag 引用，而是通过 Liquid 变量访问。依赖无法按页面精确追踪，除非给 drop 加钩子。更简单的做法是做全局判断：任一 data 文件的 mtime 变了就强制全站重新生成。
- 主题 data（`theme.data_path`）也走 `DataReader`，需要同样处理。
- 改动会影响：
  - `.jekyll-metadata` 的 Marshal 内容和格式。旧元数据需兼容，`read_metadata` 有 TypeError 和 ArgumentError 的回退。
  - `Cleaner`（`cleaner.rb:34` 只是排除 metadata 文件）。
  - `test_regenerator.rb` 里 `metadata.size == 1` 的断言（`:114`）。如果 data 文件被塞进 metadata 就会破坏它。
- 另一个不确定点：data 文件被删除、新增、改名时如何处理。

**【4 现有测试与约定】**
- `test/test_regenerator.rb`：
  - `:27-31` 断言 `assert @regenerator.regenerate?(@page)`，即未见过的文件需要重新生成。
  - `:55-57` 断言未变更时 `refute @regenerator.regenerate?(@page)`。
  - `:89-90` 断言 `Object.new` 总是重新生成。
  - `:114` 断言 `assert_equal 1, @regenerator.metadata.size`。
  - `:118-124` 是依赖被删除时的处理。
- `features/incremental_rebuild.feature:60-107`：include 变更、自定义 collections_dir 和主题场景。这些都是 cucumber 风格，用 "I wait 1 second" 加改文件再构建。
- `test/test_data_reader.rb` 只测解析，没有增量相关测试。
- 文档 `docs/_docs/configuration/incremental-regeneration.md:22-26`：写着 "the only types of dependencies tracked are includes ... and layouts"，`site.posts` 迭代不被检测。这与题面期望存在冲突，也说明这是文档化的已知局限。如果修复，文档也应更新，隐藏测试大概率不测这一点。
- 没有找到外部规范或参考实现。

**【5 边界与隐含要求】**
- data 的位置：站点 `_data`、`data_dir` 配置、主题 data、嵌套子目录。
- 新增、删除、改名 data 文件时，旧 metadata 里没有对应记录。
- 首次运行（无 metadata）和旧格式 metadata 的兼容。
- mtime 精度：测试里用了 `wait 1 second`。
- 没改任何文件时仍要保持增量（`refute regenerate?`），不能退化成每次全量。
- `disabled?`（未开启 incremental）时不应该做任何额外工作或写 metadata。
- 非 Page 和 Document 对象（static file 等）的处理保持原样。
- 依赖粒度：整站全量刷新，还是只刷新用到 data 的页面。后者需要追踪 Liquid 访问，难度大得多。
- `regenerate?` 的缓存和 `add` 对 cache 的副作用。

**【6 改动规模】**
- 估计 2 到 3 个文件，几十行以内：`regenerator.rb` 为主，可能加 `site.rb` 或 `reader.rb` 或 `data_reader.rb` 登记 data 路径。再加测试，文档可选。
- 属于局部修补加少量新增状态，不贯穿多层。前提是采用全局判断的方案。如果要按页面追踪就是跨层的大改动。

**【7 难点一句话】**
难点不在代码量，在设计取舍：data 没有现成的依赖登记点，需要决定"全站强制重新生成"还是精细追踪，并让新增或删除 data 文件以及 metadata 兼容的情况都正确，同时不破坏 `test_regenerator.rb` 里对 metadata 内容的既有断言。