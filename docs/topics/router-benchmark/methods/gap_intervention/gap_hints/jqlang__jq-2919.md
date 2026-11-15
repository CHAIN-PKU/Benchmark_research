## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. (1) src/main.c 主循环 `--` 分支目前要求 program 已存在，否则 usage 报错，这是要改的点；(2) args_done 分支与 !isoptish 分支各有一份重复的 --args/--jsonargs/文件处理逻辑，需保持一致；(3) -f/--from-file 下 program 的处理，决定 `--` 之后第一个参数是程序还是文件；(4) usage() 文本、jq.1.prebuilt、docs 手册、NEWS 可能需说明 `--`。

B. `jq -- '-1'` 等以 - 开头的程序；`--` 之后的 --zorch 在 --args/--jsonargs/文件模式下的处理；多个 `--`；`--` 后无参数或仅有程序；--args/--jsonargs 在 `--` 前后的位置；程序已给出后的 `--` 旧行为不能破坏。

C. 选项可出现在非选项参数之后的现有语义须保持，无 `--` 时 --zorch 仍报 Unknown option；isoptish/isoption 判定需让 `--` 先于其处理；tests/shtest 有 --args/--jsonargs 用例可参照；NEWS 与手册对 --args/--jsonargs 的描述需一致。

D. (1) 题面原例，positional 应含 --zorch；(2) `jq -n -- '-1'` 与 `jq -n --jsonargs -- '$ARGS' 1 '"x"' --`；(3) 回归：无 `--` 时 --zorch 仍报错，单独 `jq --` 仍为用法错误，`jq . -- file` 旧行为不变。
