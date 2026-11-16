# 仓库档案：jekyll doctor 冲突警告（同一文件相对路径和绝对路径各报一次）

我没有运行代码，也没有实际复现。下面的"根因"是读代码后的推断，其中 Page 为什么会读到 `_guides` 这一步没有查证。

## 【1 题面要点】
- 期望行为：同一个源文件不应被报成"多个文件共用同一目标"的冲突。
- 题面给了日志，没给复现配置，也没给修法建议。
- 日志里同一个目标出现两条来源：
  - `_guides/800-guide-django-rest-server-user-tracking.md`（相对路径）
  - `/Users/Xingheng/repos/_guides/800-...md`（绝对路径）
- 题面只写了一句猜测："Seems it thinks full path … is a different file than relative path"。
- 目标是 `_site/guides/.../index.html`，所以 `_guides` 是一个 `output: true` 的 collection。

## 【2 相关代码】
- `lib/jekyll/commands/doctor.rb:126-135` `destination_map(site)`：
  - 遍历 `site.each_site_file`，用 `thing.destination(site.dest)` 作键，`thing.path` 作值，聚合成 `result[dest_path] << thing.path`。
  - **最可能的修改点**：在这里对路径去重，或统一路径形式。
- `doctor.rb:68-82` `conflicting_urls`：`paths.size > 1` 就报冲突，并逐条打印 `" - #{path}"`。
- `lib/jekyll/site.rb:362-368` `each_site_file`：依次遍历 `pages`、`static_files_to_write`、`docs_to_write`。
- 各类型的 `path` 形式不一致，这是冲突的来源：
  - `lib/jekyll/document.rb:8` `attr_reader :path`，`:44` 的 `@path = path` 是构造时传入的绝对路径。
  - `lib/jekyll/page.rb:139-141` `path` 返回 `data.fetch("path") { relative_path }`，是相对 source 的路径（`:144-146`）。
  - `lib/jekyll/static_file.rb:41-47` `path` 由 `@base`、`collections_dir`、`@dir`、`@name` 拼成，通常是绝对路径。
- 推断的根因：同一个文件既被当作 Page（相对路径）读入，又被当作 Document（绝对路径）读入。Page 的读入路径是 `reader.rb:55-80` 的 `read_directories`，经 `retrieve_pages`（`:117`）进入。Document 的读入路径是 `collection.rb:57-70` 的 `read` 和 `read_document`。
- 第二个来源为什么存在，我没有查证。猜测是用户的 `include:` 配置让 `_guides` 被 `read_directories` 当作普通目录读了。

## 【3 并列与牵连】
- `doctor.rb:141-146` `case_insensitive_urls` 是并列实现，处理"只有大小写不同"的 URL，用的是 `site.pages + site.docs_to_write`。它按 dest 去重，不涉及 path，所以大概不用改。
- `site.rb:229` 的 `Jekyll::Commands::Doctor.conflicting_urls(self)` 是第二个调用点，在构建时也会触发冲突警告。
  - 只要改 `destination_map`，`jekyll doctor` 和构建两处都生效。
- 冲突信息只由 doctor.rb 里的 `Jekyll.logger.warn` 输出。
- 如果改成"更早去重"（让文件不被重复读入），影响面会扩大到 reader 和 collection，风险更高。
- 如果改的是路径的形式（比如把 `Document#path` 或 `Page#path` 统一），会影响 `relative_path`、frontmatter defaults 和 Liquid 里的 `page.path`，有明显的副作用。

## 【4 现有测试与约定】
- `test/test_doctor_command.rb`：
  - 只有 "URLs only differ by case" 一个 context（`:7`）。
  - 其中有 `should "return success on a valid site/page"`（`:12`，断言 `assert_equal "", output`，`:22`）和 `should "return warning for pages only differing by case"`（`:26`，`assert ret`，`:34`）。
  - **没有直接测试 `conflicting_urls` 的 Ruby 单测。**
- `features/permalinks.feature:172-179` 是冲突场景：
  - 期望输出里同时出现 `_site/amazing.html`、`awesome.md`、`cool.md`、`_posts/2009-03-27-rover.markdown`、`_puppies/rover.md`。
  - Pages 和 Documents 都以**相对路径**出现。
  - 这条 feature 不能被破坏：真冲突仍要列出所有来源，并保持现有的相对路径形式。
- `features/permalinks.feature:195-198` 是 redirect-from 不算冲突，对应 `doctor.rb:137-139` 的 `allow_used_permalink?`。
- 隐藏测试很可能新增一个 doctor 的 Ruby 单测（同一文件相对/绝对路径各一份、期望无冲突），或新增 feature。
- 无外部规范。
- **与题面的潜在冲突**：feature 里的真冲突输出用相对路径，所以 `destination_map` 里大概需要把路径统一成相对 source 的形式，而不是绝对路径。

## 【5 边界与隐含要求】
- 判断"同一文件"要把路径统一后比较。`Document#path` 是绝对路径，Page 的是相对路径，有 `collections_dir` 时前缀也不同（`document.rb:112` 的 `relative_path` 是相对 `collections_path`，不是相对 source）。
- 路径统一要用 `site.source` 去前缀，不能用 `collections_path`，否则 Page 和 Document 仍然对不上。
- 真冲突不能被误去重：
  - 不同文件映射到同一目标，必须仍然报冲突。
  - 同一个文件重复出现，才应该合并。
  - 合并后如果只剩 1 项，就不报。
- 去重后输出的路径形式要稳定：保持相对路径，避免 feature 断言里的 `_posts/...`、`_puppies/rover.md` 失败。
- 主题（theme）里的文件路径形式不同（`page.rb:42-43` 用 `in_theme_dir`），统一路径时不要把主题文件误判为 source 下的文件。
- Page 的 `data["path"]` 可以被 frontmatter 覆盖（`page.rb:140`），此时 `path` 不是文件路径。
- `site.dest` 在 source 内时，`retrieve_dirs`（`reader.rb:106`）有跳过逻辑，别受影响。
- Windows 路径分隔符：用 `File` 或 `Pathname` 的 API，不要手写 `sub("/")`。

## 【6 改动规模】
- 最小方案：改 `doctor.rb` 一个文件、`destination_map` 一处（约 3-6 行），加 `.uniq` 或把路径转成相对 source，再补一个测试。
- 局部修补，不需要新增结构。
- 如果要求同时消除重复读入，才会牵涉 reader、collection，规模大一个量级。

## 【7 难点一句话】
改动本身很小，难在判断"同一文件"该用什么路径形式比较：Page、Document、StaticFile 的 `path` 各不相同，真冲突的输出又必须保持现有的相对路径，而 Page 为什么会读到 `_guides` 我也没有查实。