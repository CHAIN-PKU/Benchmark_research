# 档案：`-w/--word-regexp` 在行首漏掉首字符

我读了 `word.rs` 全文、`config.rs` 的 `into_word`、`matcher.rs` 的 word 配置和选择逻辑，还搜了 `tests/`。没有实际运行复现。下面第 2 部分的根因是我读代码推断的，没有跑过验证。

## 【1 题面要点】
- **要求的行为：** `-w` 的效果应与给模式两端加 `\b` 一致。手册原话：“This is roughly equivalent to putting \b before and after all of the search patterns.”
- **复现数据**（三行文件）：
  ```
  some.domain.com
  some.domain.com/x
  some.domain.com
  ```
- **复现命令：** `rg -w "([\w]+[.])*domain[.](\w)+"`
- **实际结果：** 第 1、3 行匹配 `some.domain.com`，第 2 行匹配成 `ome.domain.com`，即丢了首字符。
- **期望结果：** 与 `rg "\b([\w]+[.])*domain[.](\w)+\b"` 相同，三行都匹配完整的 `some.domain.com`。
- **没有给出的内容：** 没给修法建议。实际输出只有截图和 gist。版本是 13.0.0，但当前快照已是 regex-automata 重写后的代码（`word.rs:9` 用 `regex_automata::meta::Regex`）。
- **注意：** 题面所说的“等价于 `\b`”并不精确。`matcher.rs:324-332` 的文档明确说 `-w` 与 `\b` 不同，`-w` 只要求两侧是非单词字符或行边界。修复不能改成真正的 `\b` 语义，否则 `-2` 之类的测试会挂。

## 【2 相关代码】
- **`crates/regex/src/word.rs:104-155` `fast_find`：最可能的根因。**
  - 它用整体正则 `(^|\W)(pat)(\W|$)` 找候选 `cand`。
  - `word.rs:136` 只在 `cand.start()==0 || cand.end()==haystack.len()` 时放弃走慢路径。
  - 随后 `word.rs:139-148` 无条件各剥掉首尾一个码点，假定它们是 `\W`。
  - 我的推断是：haystack 是多行缓冲区时，第 2 行行首的 `^`（`StartLF`，见 `config.rs:350-356`）在偏移 16 处匹配，此时 `cand.start()!=0`。
  - 于是首字符 `s` 被当成 `\W` 剥掉，得到 `ome.domain.com`。
  - 第 1 行 `cand.start()==0` 走慢路径，所以正确。
  - 第 3 行看起来正确，大概是前面的 `\n` 被 `\W` 分支吃掉了。我没有验证这一点。
  - 为什么第 2 行才出错，我没有完全推清：`/x` 让右侧的 `\W` 分支匹配 `/`，而不是靠 `$`。
  - `word.rs:150` 用 `self.original.is_match(&haystack[cand])` 做二次确认，`original` 是 `into_anchored` 的版本。去掉首字符后 `ome.domain.com` 仍满足原正则，所以确认通过，错误被掩盖。
- **`word.rs:162-188` `find_at`：** 先 `fast_find`，`Err(())` 时用 `search_captures` 取第 1 组（慢路径）。
- **`word.rs:202-212` `captures_at`：** 直接走捕获，不经过 `fast_find`。
- **`config.rs:305-326` `into_word`：** 构造 `(?m:^|\W)(pat)(?m:$|\W)`，把用户模式放进第 1 组。
- **`matcher.rs:411-423` `RegexMatcherImpl::new`：** 选择走 Word 还是 Standard。`whole_line` 开启时不用 WordMatcher。

## 【3 并列与牵连】
- **`fast_find` 的影响面：** 它只被 `find_at` 调用。行搜索、`-o`、高亮等都经 `find_at`/`find`，所以修这一处就覆盖全部。
- **`captures_at` 不受影响：** 它走慢路径，应该没有这个 bug。这是一个对照：慢路径的第 1 组才是权威结果。
- **其他层次未看：** 我没检查 `crates/searcher` 是否按行切分 haystack，也没检查 `crates/printer` 的替换和高亮是否另有 word 相关处理。
- **并列实现：** 我没有找到其他与 `-w` 并行的实现。

## 【4 现有测试与约定】
- **`word.rs:249-279` `various_find`**，例如：
  - `assert_eq!(Some((1, 4)), find(r"foo", "!foo("))`
  - `assert_eq!(Some((3, 8)), find(r"!?foo!?", "##\n!foo!##"))`
  - `assert_eq!(Some((3, 7)), find(r"f?oo!?", "##\nfoo!##"))`
  - 这些已经覆盖了含 `\n` 的 haystack，但没有“行首是单词字符”且 `cand.start()>0` 的用例。
- **`word.rs:283`** `regression_dash`：`find(r"-2", "-2") == Some((0,2))`。
- **`word.rs:291-303`** `various_captures`：捕获 API 的对照断言。
- **`matcher.rs:840-846`** `word()` 测试：对比 `-2` 在 word 与 `\b-2\b` 下的差异，确认 `-w` 与 `\b` 有意不同。
- **集成测试：** `tests/misc.rs:137` `word`（`-w as sherlock`）；`tests/regression.rs:462` `r506_word_not_parenthesized`（`-w -o min|max`）。
- **约定：** 回归测试在 `tests/regression.rs`，用 `rgtest!`，按 issue 号命名。单元测试写在 `word.rs` 底部。
- **与题面的冲突：** 题面说“等价于 `\b`”，文档说“不等价”。正确行为以 `(^|\W)(pat)(\W|$)` 语义为准，修复后三行都应匹配完整的 `some.domain.com`。

## 【5 边界与隐含要求】
- **行首不在偏移 0：** 多行 haystack 中，`^` 在任意行首匹配，`cand.start()>0` 但左侧并非 `\W`。
- **行尾对称：** `$` 匹配在非 haystack 末尾的 `\n` 之前时，`cand.end()` 也未必等于 `haystack.len()`，右侧同理会多剥或少剥。
- **CRLF 模式：** `StartCRLF`/`EndCRLF`（`config.rs:351-362`）下，`\r\n` 可能是两字节，剥掉一个码点不对。
- **多字节首字符：** 剥离用 `decode_utf8`，修复后要保证不会切断码点。
- **原模式可匹配空串：** `word.rs:146` 已有 `new_start > new_end` 的处理，改动后要保持。
- **`at>0` 的 span：** `Input::new(haystack).span(at..)` 下，`^` 的语义要核对。
- **性能：** `fast_find` 是有意为之的快路径，修复不应让大多数情况都落入慢路径。

## 【6 改动规模】
- **规模：** 局部修补，1 个文件（`word.rs`）、1 到 2 处，加 1 到 2 个新测试。
- **做法：** 可以在 `fast_find` 里判断候选实际匹配的是 `\W` 还是行锚，或检查被剥字符确实是 `\W`，不满足就 `Err(())` 走慢路径。也可以直接在剥离前检查首尾码点。
- **不需要：** 新增结构或贯穿多层的改动。

## 【7 难点一句话】
难点在定位：错误被 `original.is_match` 的二次确认掩盖，且只在“行首落在偏移 >0”时触发，所以必须想到多行缓冲区里 `^`（`StartLF`）会在非零偏移匹配；改法本身很小，但要覆盖行尾、CRLF 和多字节这些对称情形，同时保住快路径。