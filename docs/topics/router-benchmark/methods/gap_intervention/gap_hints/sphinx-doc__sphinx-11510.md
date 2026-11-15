## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) sphinx/directives/other.py Include.run 调用 docutils 基类 run() 自行读文件,绕过 sphinx/io.py SphinxStandaloneReader.read_source(source-read 仅在此触发),修复应落在 Include 一侧,先查清基类读取路径;2) 被包含文件触发事件时的 docname 取值(env.docname 是主文档;查 env.path2doc/relfn2path/note_included),source 仍须是单元素列表;3) include 的 literal/code/start-line/end-before 等选项在读取前后如何生效,处理顺序要一致。
B. 1) 同一文件被多文档或多次包含,事件应每次生效;2) :literal:/:code:/行范围选项下替换仍生效且不破坏行号;3) <...> 标准 include 早退分支与嵌套 include。
C. 1) doc/extdev/appapi.rst 事件顺序(约160-180行)与 source-read 描述(约251行),核对是否需补充;2) 现有订阅者 sphinx/ext/duration.py on_source_read、intersphinx install_dispatcher、doc/conf.py linkify_issues_in_changelog 在额外触发下不应出错;3) tests/test_directive_other.py 与 tests/roots 下 include 相关测试根目录的结构,CHANGES 条目惯例。
D. 1) 按题面复现,主文档与被包含文件两处都被替换;2) 被包含文件被两个文档引用、以及只含 include 的文档;3) :literal:/:start-line: 与嵌套 include,并跑 test_directive_other、test_build_html 回归。
