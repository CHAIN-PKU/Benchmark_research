**档案：jq `--jsonargs` 遇到非法 JSON 时断言崩溃**

**【1 题面要点】**
- 要求的行为：`--jsonargs` 收到非法 JSON 文本时，应当尽早报错，而不是继续运行。
- 复现命令：`jq -n --jsonargs '$ARGS' 123 'invalid json'`。输出打印到 `123` 之后，`jv_dump_term` 断言失败 `0 && "Invalid value"` 并 abort。
- 另一个现象：`$ARGS.positional[0,1]` 输出 `123` 和 `null`，不会崩溃。
- 期望输出的原文：“Expected behaviour i think would be to error earlier on invalid JSON”。
- 题面没有给具体的报错文案、退出码或修法。“error earlier”只是提问者的个人想法（“i think”）。

**【2 相关代码】**
- `src/main.c:315-340` 的参数循环里有两处 `ARGS = jv_array_append(ARGS, jv_parse(argv[i]));`：
  - 第 320 行在 `args_done` 分支，即 `--` 之后。
  - 第 333 行在 `!isoptish` 且已有 program 的分支。
  - 两处都没有检查 `jv_parse` 返回的是否为 invalid，于是 invalid 值被放进数组。
- `src/main.c:476-491` 是 `--argjson`，已有现成的处理方式：
  - `jv v = jv_parse(...)`
  - `if (!jv_is_valid(v)) { fprintf(stderr, "%s: invalid JSON text passed to --argjson\n", progname); die(); }`
- `src/main.c:98-102` 是 `die()`：打印两行帮助提示后 `exit(2)`。
- `src/main.c:635-645`：把 `ARGS` 包成 `$ARGS`。这里不是出错点。

**【3 并列与牵连】**
- 同一个文件里有两处并列的 `jv_parse` 调用，必须一起改，只改一处会留下 `--` 之后的路径。
- `--argjson` 已有的检查可作为参考。
- `--slurpfile` 和 `--argfile` 用 `jv_load_file`，失败时 `goto out` 并返回 `JQ_ERROR_SYSTEM`，是另一种错误风格，可对照。
- 改动只影响命令行解析，不触及库代码。
- 错误路径用 `die()` 直接 `exit`，不会走到 `out:` 清理，所以不涉及资源释放。

**【4 现有测试与约定】**
- `grep` 在 `tests/` 里没搜到 `jsonargs` 或 `argjson`，目前没有针对这些选项的测试。
- 命令行类测试在 `tests/shtest`，是 shell 脚本。
  - 常用写法是 `$JQ ... || ret=$?`，然后检查退出码（例如 `shtest:104`、`131-134`）。
  - 隐藏测试很可能加在这里，断言非零退出码，可能还会检查 stderr 里有没有报错文案。
- 手册 `docs/content/manual/manual.yml:283-292` 只说“Remaining arguments are positional JSON text arguments”，没有规定出错行为。
- 没有外部规范与题面冲突。
- 退出码和文案没有明文约定，只能靠 `--argjson` 的先例推测：文案 `invalid JSON text passed to --jsonargs`，退出码 2。

**【5 边界与隐含要求】**
- 非法 JSON 出现在 `--` 之后时也要报错。
- 后面还有第二个非法参数时，应在第一个就退出。
- 不能让合法的值（如 `123`、`null`、`"s"`）被误判。
- 空字符串参数的 `jv_parse` 结果需要确认。如果返回 invalid，会被当成错误，这可能是预期行为。
- 一个细节：`jv_parse` 失败时返回的 invalid 可能带消息，可以把消息一起打出来，也可以不带。
- 退出码如果不对（比如用了 `JQ_ERROR_SYSTEM`=2 还是 `die` 的 2），具体数值要和测试一致。目前两者碰巧都是 2。

**【6 改动规模】**
- 只改 `src/main.c`，两处，每处几行。
- 属于局部修补，不新增结构。
- 可选：加一个 `tests/shtest` 用例，并更新手册和 `NEWS`。

**【7 难点一句话】**
修法很直接，是照抄 `--argjson` 的检查并覆盖两个调用点；真正的不确定性在于隐藏测试对报错文案和退出码的具体要求，题面没有给出这两项。