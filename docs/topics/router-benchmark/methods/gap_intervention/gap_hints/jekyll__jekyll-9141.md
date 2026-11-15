## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**需求落差清单（jekyll__jekyll-9141）**

查到的情况：`Doctor.conflicting_urls`（lib/jekyll/commands/doctor.rb:68-82）用 `destination_map`（第126行）按目标路径分组 `thing.path`。`Page#path`（page.rb:139）返回相对路径，`Document#path`（document.rb:44）和 `StaticFile#path`（static_file.rb:41）返回绝对路径，与题面里一条相对、一条绝对吻合。未运行复现，只是推断：同一物理文件很可能被当成 Page 和 Document 各读了一次。

A. 题面没点名、但很可能要一起处理的位置
1. 先弄清重复条目是怎么产生的，再决定改哪里：看 lib/jekyll/reader.rb 的目录读取、collection.rb 的 read/entries/filtered_entries、entry_filter.rb（下划线目录是否因 include 配置被当作普通页面遍历）。只改 doctor 报告能让警告消失，但同一文件仍可能被构建两次，要判断问题在报告层还是读取层。
2. destination_map 里 Page/Document/StaticFile 的 path 格式不一致。若在报告层处理，要想清楚怎么判断两条记录是同一个物理文件（例如统一成绝对路径），并注意 Page#path 可能被 front matter 的 path 覆盖。
3. site.rb:229 也调用 conflicting_urls，不只 jekyll doctor，构建时的警告也走这条路径，两处行为要一致。

B. 题面没给例子、但很可能被检查的输入/边界情况
1. 同一文件的两条记录（一条绝对、一条相对，目标路径相同）不应再报冲突。
2. 两个确实不同的文件指向同一 permalink，仍必须报冲突，不能因修复而漏报。
3. collections_dir 非空时 Document 与 StaticFile 的路径拼法不同（static_file.rb:42-45），要核对该配置下的结果。

C. 仓库里已有的约定、文档或测试
1. 查 test/test_doctor_command.rb（或同类文件）里现有 conflicting_urls 用例，保持输出格式和返回值（有冲突返回 true）。
2. 看 allow_used_permalink?（doctor.rb:137）已有的豁免约定，新逻辑写法与之一致。
3. 若改读取层，核对 test/test_collections.rb、test/test_site.rb、test/test_entry_filter.rb 里关于 include/exclude 的既有断言。

D. 提交前建议额外自测
1. 构造 _guides 集合加 include: [_guides]（或类似能触发重复读取的配置）的站点，确认修复前有警告、修复后消失。
2. 构造两个不同源文件、同一 permalink 的站点，确认仍然警告。
3. collections_dir 设为非空，重复第1项，并跑一遍现有 doctor 相关测试。
