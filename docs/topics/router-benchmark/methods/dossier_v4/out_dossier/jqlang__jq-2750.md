# 仓库档案:jq 中两个 try/catch 用管道连接时,第一个 try 的 catch 误捕获了后续错误

我没有运行代码,下面都是读源码得出的。

## 【1 题面要点】
- 要求的行为:`try A catch H1 | try B catch H2` 中,B 抛出的错误只能被 H2 处理。第一个 try 的 body A 已经正常产出值,所以 H1 不应该执行。
- 复现命令:`jq -n 'try null catch error(["catch-a", .]) | try error("error-b") catch error(["catch-b", .])'`。
- 实际输出:`["catch-a",["catch-b","error-b"]]`。期望输出:`["catch-b","error-b"]`,题面说 gojq 的行为符合预期。
- 题面没有给修法建议,只说"可能与 #1859 相关"。没有给测试文件或具体断言。

## 【2 相关代码】
- `src/compile.c:1052-1074` 的 `gen_try(exp, handler)`:生成 `FORK_OPT <handler addr>; exp; JUMP <end of handler>; handler`。
  - 注释写明"handler 只在回溯到 FORK_OPT 且带错误时执行"。
- `src/execute.c:811-817`:`FORK_OPT`、`DESTRUCTURE_ALT`、`FORK` 正向执行时只做 `stack_save(jq, pc-1, ...)`,留下一个回溯点。
- `src/execute.c:819-839` 的 `ON_BACKTRACK(FORK_OPT)`:
  - 如果 `jq->error` 有效(没有错误,即 `empty`),就继续回溯。
  - 否则视为 EXP 里抛出了异常,把错误消息压栈并跳到 handler。
- 根因判断:body 产出值后,`FORK_OPT` 的回溯点还留在栈上。try 之后(管道右侧)抛出的错误回溯时遇到它,就被当成 body 里的异常。
  - 运行时没有"body 已经退出"的标记,无法区分"错误来自 body 内部"和"错误来自 body 之后"。
- `src/execute.c:795-809` 的 `BACKTRACK`/`do_backtrack`:`stack_restore` 取出回溯点。
- `src/execute.c:395-399`:回溯时 `raising = !jv_is_valid(jq->error)`。
- `src/execute.c:333-337` 的 `set_error`:把错误记在 `jq->error`。
- `src/opcode_list.h:16`:`OP(FORK_OPT, BRANCH, 0, 0)`。修复很可能要在这里加新 opcode。
- `src/parser.y:382-402`:三处调用 `gen_try`,分别是 `try catch`、`try` 无 catch 和 `?` 后缀。
- `src/parser.c` 是生成文件,留在仓库里,改 `parser.y` 时它会一起变。

## 【3 并列与牵连】
- 并列实现 `DESTRUCTURE_ALT`(`compile.c:778-821`、`970`、`1015`,`execute.c:812`、`820`)和 `FORK_OPT` 共用同一段回溯处理代码。它是 `?//` 解构备选,原理相同,但是否有同样的泄漏需要核实。
- 其它 `gen_try` 调用点:
  - `compile.c:1089` 的 `gen_label`,即 `label $x | ... break $x`。`limit`、`first`、`until` 等很多 builtin 都用它(`builtin.jq:23`、`148`、`157`、`168`)。
  - 这里的 break 机制靠 try/catch 实现:`error` 带 `__jq` 标记对象。改 `FORK_OPT` 语义会直接影响 label/break。
  - label 的 handler 是 `gen_cond(cond, BACKTRACK, error)`,同样会带着泄漏问题。
- `gen_try_handler`(`compile.c:1037`)靠 `.__jq` 判断来重新抛出内部错误(break 标记)。
- `EACH_OPT`(`execute.c:723-739`,即 `.[]?`)是另一套机制,它自己处理错误。
- `builtin.jq:198` 的 `inputs` 用 `try repeat(input) catch if .=="break" ...`。
- 路径表达式(`path(...)`、`PATH_BEGIN`/`PATH_END`,`execute.c:667`)与 try 交互,新增 opcode 要保证 `path()` 内的 try 不被破坏。
- 修改 opcode 后,`src/bytecode.c` 的 dump 和 `opcode_list.h` 的栈效应声明需要同步。

## 【4 现有测试与约定】
- `tests/jq.test:1223-1225`:`[.[]|try if . == 0 then error("foo") elif ... catch .]` 期望 `["foo","Cannot index number with string \"a\"",3]`。`1227-1233` 测 `?` 与 `empty`。`1235` 测 `$__loc__`。
- `tests/jq.test:177` 测 `.a[]?`。`1782`:`. |= try . catch .`。`1830`:`try input catch .`。
- 这些测试里的错误都发生在 try body 内部,没有任何一条覆盖"管道后续错误"的情形。题面期望与现有测试不冲突。
- 约定:
  - 外部规范只有题面里的 gojq 行为和 jq 手册对 try 的描述(手册路径我没找到,`docs/content/manual/dev/manual.yml` 不存在)。
  - 没有找到参考实现。
- 隐藏测试大概率是在 `tests/jq.test` 加几条类似题面的用例,可能要求带 `%%FAIL` 或验证输出,这点是推测。

## 【5 边界与隐含要求】
- body 产出多个值:`try (1,2,error("x")) catch .` 之类的情形里,body 内的后续错误仍要被捕获。因此"产出第一个值后就禁用 catch"是错的。
- body 产出值后,下游再回溯回 body 要继续取下一个值,此时错误又应当重新被 try 捕获。
- 嵌套 try,以及 handler 内部再抛错。
- 下游错误穿过 try 时必须原样传播。
- `limit`、`first`、`label/break` 在 try 里或包含 try 时语义不变。
- `.a?` 无 catch 的形式。
- `path(try ...)` 以及 `reduce`/`foreach` 内的 try。
- `error(null)` 的处理。
- 栈和内存:新增的标记不能泄漏 `jv`。

## 【6 改动规模】
- 预计 3-5 个文件:`src/execute.c`、`src/compile.c`、`src/opcode_list.h`,可能还有 `src/bytecode.c` 和 `tests/jq.test`。每个文件各改几处。
- 这不是单点补丁,需要新增 opcode 或栈上标记,让运行时区分"在 body 内"和"body 之后"。
- 需要同时改编译期(`gen_try` 在 body 前后插入标记指令)和运行期(回溯时识别)。

## 【7 难点一句话】
难在这个 bug 的根源是回溯点没有"作用域结束"的概念,正确修法必须新增运行时机制,让它在 body 产出值后失效、下游回溯回 body 时又能恢复,同时不能破坏 label/break、`limit`、`path()` 和 `?//` 等依赖现有 `FORK_OPT` 语义的地方。