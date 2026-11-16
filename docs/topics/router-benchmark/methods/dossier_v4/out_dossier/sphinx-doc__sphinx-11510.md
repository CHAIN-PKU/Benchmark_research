正在收尾：已经查完相关代码，现在输出档案。docutils 的 `Include.run` 源码我没能直接读到（沙箱拦了命令），下面关于它的描述来自我对 docutils 的一般了解，不是对本仓库的查证。

# 仓库档案

## 【1 题面要点】
- 要求的行为：`source-read` 事件要对被 `.. include::` 的文件也生效。
- 题面给了完整复现：conf.py、index.rst、`something-to-include.rst`，以及一个把 `&REPLACE_ME;` 换成 `REPLACED` 的扩展。
- 期望输出：`index.html` 里两处都是 `<p>REPLACED</p>`。
- 实际输出：被包含文件里仍是 `<p>&amp;REPLACE_ME;</p>`。
- 题面没有给修法建议，只有一句观察：「the function actually gets called for something-to-include.rst file and its content is correctly replaced in source[0], it just does not make it to the final HTML」。
- 这句话说明：对被包含文件，事件似乎被触发过，但改动没进入文档。我没有复现，没法核实这一点。从代码看，我没找到 `Include` 会触发 `source-read` 的路径，这个说法可能不准。

## 【2 相关代码】
- `sphinx/io.py:108-115`，`SphinxStandaloneReader.read_source`：读入 `self.source.read()`，构造 `arg=[content]`，调用 `env.events.emit('source-read', env.docname, arg)`，返回 `arg[0]`。这是仓库里**唯一**触发该事件的地方。它只处理顶层文档，不处理 include 进来的文件。
- `sphinx/directives/other.py:365-379`，`class Include(BaseInclude, SphinxDirective)`：
  - 处理 `<...>` 形式的标准 include，直接 `super().run()`。
  - 其余情况用 `relfn2path` 解析路径，写回 `self.arguments[0]`，调用 `env.note_included(filename)`，再 `super().run()`。
  - 文件内容由 docutils 父类 `run()` 读取，并通过 `state_machine.insert_input` 插入，Sphinx 没有介入这一步。这是最可能要改的位置。
- `sphinx/environment/__init__.py:568`，`note_included`：记录被包含的文件，`self.included[self.docname]` 在 :577 写入。
- `sphinx/events.py:40`：声明了 `'source-read': 'docname, source text'`。
- `doc/extdev/appapi.rst:251-261`：事件文档，写的是「source 参数是单元素列表，内容是源文件内容」。

## 【3 并列与牵连】
- `LiteralInclude`（`sphinx/directives/code.py:385`，读取逻辑在 `LiteralIncludeReader` :178）读取的是代码文件，通常不应该被当作 reST 源码处理。题面只提到 `include`，不要顺带改它。
- `io.py` 里的 `SphinxI18nReader` 和 `SphinxStandaloneReader` 并列，但 i18n 那边没有 `read_source`。
- `doc/conf.py:235` 的 `linkify_issues_in_changelog`、`sphinx/ext/duration.py:55`、`sphinx/ext/intersphinx.py:691` 都订阅了 `source-read`。
  - 一旦被包含文件也触发该事件，这些回调也会收到被包含文件的内容。
  - 它们拿到的 `docname` 是什么，需要决定（见第 5 条）。
  - `duration` 按 docname 计时，可能被影响。
- 包含 `<...>` 的标准 include 走 `super().run()`，不经过 Sphinx 的路径处理。

## 【4 现有测试与约定】
- `tests` 里没有任何 `source-read` / `source_read` 的测试，需要新增。
- `tests/test_directive_other.py` 只有 toctree 的 `includefiles=[...]` 断言（:24、:42 等），与 include 指令无关。
- `tests/roots/test-root/includes.txt:11,13,22,101` 已有 `.. include::` 用例，改动不能破坏这些。例如 `wrongenc.inc` 是错误编码的用例，`/subdir/include.inc` 是绝对路径的用例。
- 文档约定是「source 是单元素列表」，题面期望与此不冲突。
- 我没找到外部规范，行为由文档和 docutils 的 `Include` 实现决定。

## 【5 边界与隐含要求】
- 被包含文件的 `source-read` 回调传入的 `docname`，是被包含文件对应的 docname，还是当前文档？
  - 题面说回调里 dump 出了 `something-to-include.rst`，暗示应该是被包含文件。
  - 它不是独立文档，不在 `env.all_docs` 里，需要用 `env.path2doc` 之类的方式转换。
- 要保留 docutils `Include` 的各种选项：`start-line`、`end-line`、`start-after`、`end-before`、`literal`、`code`、`parser`、`encoding`、`tab-width`。
  - 如果自己重写读取逻辑，这些都要处理。
  - 如果用事件对读入的文本做拦截，则要保证改动在这些选项之前生效。
- 要保留编码错误的处理，以及不存在文件时的错误报告。
- `literal` 和 `code` 选项下的内容也会被事件修改。题面的场景（在 literal block 里替换）恰好需要这一点，所以不能只处理 reST 解析的情况。
- 嵌套 include 要能递归生效。
- `include` 的路径依赖当前 env 的 `docname`，处理时不能让它被意外改写。
- 增量构建：被包含文件的依赖记录（`note_included`、`note_dependency`）要保持原样。
- 并行读取（`parallel_read_safe`）下不能依赖全局状态。

## 【6 改动规模】
- 预计改 1 到 2 个文件：主要是 `sphinx/directives/other.py` 的 `Include`，可能要新增一个读取并触发事件的方法或子类。
- 另外要新增测试和测试 root，并更新 CHANGES 和 `appapi.rst` 的说明。
- 属于局部修补，不贯穿多层。

## 【7 难点一句话】
难点在于 docutils 的 `Include.run` 不暴露读取内容的钩子，要在不丢失各个 include 选项、编码处理和路径语义的前提下，让被包含文件的内容经过 `source-read` 事件，并决定回调拿到的 `docname` 是什么。