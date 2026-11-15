## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
1. 数据文件由 `lib/jekyll/readers/data_reader.rb` 的 `read_data_to` 和 `read_data_file` 读取，由 `lib/jekyll/reader.rb` 的 `read_data` 调用。这里完全没有和 `site.regenerator` 打交道，所以数据文件的 mtime 从未被记录。修复可能要从这条读取路径入手，而不只是改 `regenerator.rb`。
2. 主题数据走的是同一个 `DataReader`，只是换了 `in_source_dir`（`site.method(:in_theme_dir)`）。注意 `regenerator.rb` 和 `Site#in_source_dir` 里的路径都是按源码目录算的。核对主题数据的路径会不会被一并处理，或者被错误处理。
3. `lib/jekyll/site.rb` 的 `write` 和 `process`，以及 `regenerator.regenerate?` 的各个分支（`Page`、`Document`、其他）。数据变化后，所有依赖数据的页面和文档都得重新生成，而不只是某一类。另外 `lib/jekyll/commands/serve.rb:149` 也调用了 `regenerate?`。
4. 已有的依赖机制是 `add_dependency(path, dep)`，它依赖 `metadata[path]` 已存在。调用点在 `renderer.rb` 的 `add_regenerator_dependencies`，以及 `tags/include.rb`。查一下数据文件该怎么挂到页面上，还是应该作为全局触发条件。同时看 `site.rb#reset` 里 `@regenerator.clear_cache` 的时机，它会影响缓存的有效性。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
1. 修改数据文件后，只触发重建。要看没有任何页面修改过时，页面是否会重新生成。
2. 子目录里的嵌套数据文件，以及 yml/yaml/json/csv/tsv 各种扩展名。
3. 新增或删除数据文件。目前 `metadata` 只处理已存在的路径，删除的文件按现有的「已删除依赖」约定处理。
4. 数据文件没变时，不应该导致全部重建。这是增量功能的前提。

**C. 仓库里已有的约定、文档或测试**
1. `test/test_regenerator.rb` 里有「handle deleted/nonexistent dependencies」「cache processed entries」「regenerate if file is modified」等用例。这些约定需要保持不变，新逻辑要和它们兼容。
2. `.jekyll-metadata` 用 Marshal 序列化，还有旧版 YAML 的兼容读取（`read_metadata`）。新增的元数据结构要能和旧 metadata 文件兼容。
3. `docs/_docs/configuration/incremental-regeneration.md` 描述了增量再生的行为。如果行为有变，可能需要同步文档。

**D. 提交前建议额外自测**
1. 构建两次，第二次之前只改 `_data/*.yml`，不改任何页面。确认输出变了。
2. 构建两次，中间什么都不改。确认没有页面被重写（可以看目标文件的 mtime）。
3. 修改嵌套目录里的数据文件，或者删除一个数据文件。确认不崩溃，并且输出正确。
