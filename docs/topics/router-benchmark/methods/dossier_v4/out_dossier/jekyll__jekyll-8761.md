# 仓库档案：`page.name` 在 post/collection 文档上为空

## 【1 题面要点】
- 期望行为：post 里的 `{{ page.name }}` 应返回文件名，"like it does with pages and is described in the docs"。
- 实际行为："It doesn't return anything on posts."
- 复现：`jekyll new blog`，在默认 post 里加 `{{ page.name }}`。
- 题面没有给期望输出的具体值（例如是否带日期前缀、是否带扩展名），也没有给修法建议。
- 文档依据：`docs/_data/jekyll_variables.yml:137-139` 写着 `page.name`："The filename of the post or page, e.g. about.md"。

## 【2 相关代码】
- `lib/jekyll/drops/document_drop.rb`
  - 第 14 行：`delegate_method_as :relative_path, :path`。
  - 第 17 行：`delegate_methods :id, :output, :content, :to_s, :relative_path, :url, :date`。
  - 第 18 行：`data_delegators "title", "categories", "tags"`。
  - **没有 `name`**。post 的 `page` 是 `DocumentDrop`，查 `name` 时先找 Drop 方法，找不到再查 front matter data，最后得到 nil。
- `lib/jekyll/document.rb`
  - 第 132-134 行：`basename` 返回 `File.basename(path)`，即带扩展名的完整文件名，例如 `2020-01-01-foo.md`。
  - 第 125-127 行：`basename_without_ext`。
  - 整个 `Document` 类里**没有 `name` 方法**。
  - `attr_reader :path, :site, :extname, ...`（第 8 行）。
- `lib/jekyll/page.rb`
  - 第 8 行：`attr_accessor ... :name`。
  - 第 13-20 行：`ATTRIBUTES_FOR_LIQUID` 里含 `name`。
  - 因此 Page 正常，只有 Document 缺失。
- `lib/jekyll/excerpt.rb:10-11`：`def_delegators :@doc, :site, :name, ...`。它把 `name` 委托给 doc，而 Document 没有该方法，所以这是一个潜在的 NoMethodError。
- `lib/jekyll/drops/excerpt_drop.rb`：继承 `DocumentDrop`，会一并继承 `name` 的行为。

## 【3 并列与牵连】
- 并列实现有两个。
  - `Page`：已有 `name`。
  - `StaticFile`：`attr_reader :name`（`static_file.rb:7`），并在 `test/test_static_file.rb:176` 断言 `"name" => "static_file.txt"`。
  - 只有 `DocumentDrop` / `Document` 没有。
- 如果在 `Document` 上加 `name`，`Excerpt` 的 `def_delegators :name` 会自然生效。如果只在 drop 上加，则不会。
  - 修在哪一层需要决定。可以是 `Document#name`，也可以是 `DocumentDrop` 里 `delegate_method_as :basename, :name`。
  - excerpt 的 `to_liquid["name"]` 也要一致。
- `Document` 下有两个相近的方法，`basename`（带扩展名）和 `basename_without_ext`。语义要选对：`name` 对应带扩展名的 `basename`。
- 序列化也受影响：`Drop#to_h`/`keys` 以及 `hash_for_json` 会多出一个 `name` 键，`collapse_document` 同理。依赖 drop 键集合或 JSON 输出的测试可能要看一下。
- 第三方插件可能已自己定义 `Document#name`，这是外部风险。

## 【4 现有测试与约定】
- `test/test_document.rb:155-161`：
  - `assert_equal "methods", @document.to_liquid["collection"]`
  - `assert_equal "_methods/configuration.md", @document.to_liquid["path"]`
  - 同类的 `name` 测试还不存在，隐藏测试大概率加在这里，形如 `@document.to_liquid["name"]`。
- `test/test_excerpt.rb:107`：`@excerpt.to_liquid["path"]`，excerpt 的 drop 有类似断言。
- `test/test_page_without_a_file.rb:65`：`assert_equal "properties.html", regular_page["name"]`，page 的 name 是带扩展名的文件名。
- 约定：`docs/_data/jekyll_variables.yml:139` 的示例是 `about.md`，带扩展名，与 `Document#basename` 一致，不冲突。
- 历史：`History.markdown:658` 写着 "Document page.dir and page.name (#7373)"，只是补了文档，没有补实现。
- 题面期望和现有代码约定没有冲突。

## 【5 边界与隐含要求】
- post 的 name 应是带日期前缀和扩展名的原始文件名，如 `2020-01-01-welcome.md`，而不是 slug。
- 自定义 collection 的文档（如 `_methods/configuration.md`）应返回 `configuration.md`，不含目录。
- 文件名含特殊字符的情况，例如测试里的 `escape-+ #%20[].md`，不能被转义或截断。
- excerpt 的 drop 也应有 `name`，并且不能因为 `Excerpt#name` 委托到不存在的方法而抛错。
- front matter 里用户自定义了 `name:` 时，现在的优先级是方法先于 data。新增方法会让 data 里的 `name` 被盖住，这是行为变化。要看是否需要保持 data 优先。
- 可能还要同步文档，比如 `variables.md` 里 `page.name` 的描述。

## 【6 改动规模】
- 最小改法：1 个文件、约 1 行，在 `document_drop.rb` 加 `delegate_method_as :basename, :name`。
- 稳妥改法：`document.rb` 加 `name`，再在 drop 里 `delegate_methods :name`，约 2 个文件、几行。
- 再加测试，约 1-2 个文件。
- 属于局部修补，不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
改动本身很小，难点在定位：先判断 `Document` 缺的是 `name` 而不是渲染问题，再决定修在 Document 还是 Drop。这个选择会影响 Excerpt 委托，也会决定 front matter 里的 `name` 是否被覆盖。