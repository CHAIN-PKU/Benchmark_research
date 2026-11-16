# 仓库档案：Style/RedundantLineContinuation 误报 `::A.prepend \` + `::B`

我没有运行复现，因为 Bash 复合命令被拦截。下面的结论都来自读代码，有一处推断未经验证，见【7】。

## 【1 题面要点】
- 期望行为：`::A.prepend \` 换行接 `::B` 时，不报 offense，也不自动修正。
- 现状：该 cop 报 "Redundant line continuation."，删掉反斜杠后代码语义变了，所以这是一个"安全自动修正"错误。
- 复现给得很完整：
  ```ruby
  module Test
    def self.setup
      ::A.prepend \
        ::B
    end
  end
  ```
  配置是 `NewCops: enable`。
- 题面特别说明："The line continuation has to be inside a method to trigger the false positive."
- 题面没有给修法建议，也没有指出根因。

## 【2 相关代码】
所有逻辑都在 `lib/rubocop/cop/style/redundant_line_continuation.rb`：
- `:81` `on_new_investigation`：用正则 `/(\\\n)/`（`:73`）扫描每个 `\`+换行。依次判断 `require_line_continuation?`（`:85`）和 `redundant_line_continuation?`（`:86`），满足条件就 `add_offense`。
- `:98` `require_line_continuation?`：几个"必须保留"的启发式的或。
- `:114` `inside_string_literal_or_method_with_argument?`：遍历 `processed_source.tokens.each_cons(2)`，对跨行的相邻 token 调用 `method_with_argument?`。
- `:161` `method_with_argument?`：当前 token 在 `ARGUMENT_TAKING_FLOW_TOKEN_TYPES`（`:79`，即 tIDENTIFIER、kRETURN、kBREAK、kNEXT、kYIELD）里，且下一个 token 在 `ARGUMENT_TYPES`（`:75-78`）里，就认为需要续行符。
- `:75-78` `ARGUMENT_TYPES`：白名单 token 列表。其中有 kDEF、tCONSTANT、tLBRACK、tLCURLY、tLPAREN_ARG、tSTRING、tSTRING_BEG 等，**没有 `tCOLON3`**，也就是前导 `::B` 的 token。
- `:131` `redundant_line_continuation?`：先用 `find_node_for_line`（`:185`）找该行的 AST 节点，再走 `argument_newline?`（`:169`）。最后把 `\` 换成 `\n` 重新解析，语法仍然有效就判定为冗余。

## 【3 并列与牵连】
- 同一个 cop 里有两条判断路径，都可能需要处理这个情况：
  - token 白名单路径：`ARGUMENT_TYPES` 加 `method_with_argument?`。
  - AST 路径：`argument_newline?` 和 `find_node_for_line`。
- 全仓库搜索 `tCOLON3`、`ARGUMENT_TYPES`，没有其他 cop 复用这些常量，所以改动不会牵连别的 cop。
- 类似的前缀 token 还有一元 `-`/`+`/`!`、`tCOLON3`、`tLAMBDA`、`tSYMBEG` 等。白名单只涵盖一部分，改的时候要决定只补 `tCOLON3`，还是整体改写判断方式。

## 【4 现有测试与约定】
spec 是 `spec/rubocop/cop/style/redundant_line_continuation_spec.rb`：
- `:373-385`：`foo do_something \ argument` 不报，用 `expect_no_offenses`。
- `:449-455`：把常量作为无括号参数的赋值，不报。
- `:764-771`：`some_method \ (argument)` 和 `some_method \ argument` 不报。
- `:773-781`：`memoize \ def do_something` 不报，用的就是 kDEF 白名单。
- `:117-162`：`return` / `break` / `next` / `yield` 带返回值的情况不报。
- 没有 `::Const` 作为参数的用例。
- 约定：新用例按 `expect_no_offenses(<<~'RUBY')` 的写法加。每个修复还要在 `changelog/` 目录下加一个 `fix_*.md` 条目，已有例子如 `fix_maintain_precedence_in_autocorrect_for.md`。
- 外部规范：Ruby 语法本身决定了去掉 `\` 之后 `::A.prepend` 换行 `::B` 会被解析成两条语句，或者语法错误。与题面期望没有冲突。

## 【5 边界与隐含要求】
- 题面特别点出"只在方法里触发"。我没弄清为什么，**需要实际跑一遍确认**。
- 前导 `::` 的各种位置：
  - 作为参数：`foo \ ::Bar`。
  - 作为带点调用的接收者：`foo.bar \ ::Baz`。
  - 带安全导航：`a&.b \ ::C`。
- 参数是 `::A::B` 这种嵌套常量时，第一个 token 仍是 tCOLON3。
- 不能误伤应当继续报的情况：`foo(bar, \ ::Baz)`、`[a, \ ::B]`。
- 隐含要求包括：现有 spec 全部保持通过，并补充 `::B` 作为参数的新用例。

## 【6 改动规模】
- 最小修法是局部修补：在 `ARGUMENT_TYPES` 里加 `tCOLON3`。
- 外加 spec 里 1–2 个用例和 1 个 changelog 文件，共约 3 个文件，改动点各 1–2 处。
- 如果要处理其他前缀 token，或者重写 AST 路径，规模会略大一些，但仍在同一个 cop 内，不需要新增结构，也不涉及多层。

## 【7 难点一句话】
改动本身很小，难点在定位根因：需要弄清为什么"只在方法里"才触发，是 token 白名单缺 `tCOLON3`，还是 AST 路径（`find_node_for_line` / `argument_newline?`）选错了节点。我没有验证过这一点，只是推断白名单缺项是其中一个原因。