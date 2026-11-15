## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名、但很可能也要一起处理的位置
1. `src/main.c` 约第 318–336 行的参数循环里，有两处并列的 `jv_parse(argv[i])`。一处在 `args_done`（`--` 之后）分支，约第 320 行。另一处在 `!isoptish` 且已有 program 的分支，约第 333 行。两处都要处理。只改其中一处，`jq --jsonargs '.' -- 'bad'` 或 `jq --jsonargs '.' 'bad'` 仍会出问题。
2. 同文件里 `--argjson`（约第 476–491 行）已经有解析失败的检查，`--slurpfile`、`--argfile` 也在附近。`--jsonargs` 的错误处理可以对照这些写法。
3. 解析结果无效时会走到 `jv_dump_term`，也就是 `$ARGS` 被打印的位置。那里的断言是症状，不是根因。根因是无效 jv 被放进了 `ARGS` 数组。

B. 题面没给例子、但很可能被检查的输入/边界情况
1. 无效 JSON 出现在第一个位置、中间位置和最后位置，行为是否一致。题面只有第二个位置的例子。
2. 空字符串参数 `''`。核对 `jv_parse` 对它返回什么，是无效值还是别的结果。
3. 不完整或截断的文本，例如 `'{'`、`'[1,'`。核对 `jv_parse` 对这类输入返回的是带错误信息的无效值，还是不带信息的无效值。
4. 无效参数之前有合法参数（如 `123`）时，是否仍应整体报错退出，而不是先输出一部分。

C. 仓库里已有的约定、文档或测试中需要核对的地方
1. `--argjson` 的报错格式是 `"%s: invalid JSON text passed to --argjson\n"`，之后调用 `die()`，退出码为 2。`--jsonargs` 的报错应保持同样风格和退出码。
2. 要核对的文档和测试：
   - `tests/shtest` 里没有 `--jsonargs` 的用例，需要看一下并考虑补测试。
   - `jq.1.prebuilt` 和 `docs/content/manual` 里 `--jsonargs` 的说明。
   - `main.c` 的 `usage()` 帮助文本（约第 89 行）。
3. `jv_parse` 失败时返回的无效值可能带错误信息（`jv_invalid_get_msg`）。可参考 `main.c` 其他地方（约第 510、628 行）的处理，也要注意 `jv_free` 和引用计数，避免泄漏。

D. 建议提交前额外自测的情况
1. `jq -n --jsonargs '$ARGS' 123 'invalid json'`：期望无断言崩溃，非零退出，stderr 有错误信息。
2. `jq -n --jsonargs '.' -- 123 'bad'`（`--` 之后）和 `jq -n '$ARGS' --jsonargs 'bad'`（选项在 program 之后）。
3. 全部合法的情况：`jq -n -c --jsonargs '$ARGS.positional' 1 '"a"' '{"x":null}' null`，输出要不变。再试 `--args` 与 `--jsonargs` 混用，后出现的选项覆盖先出现的，这个行为也要不变。
