## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名、但很可能也要一起处理的位置
1. 选项定义在 src/uu/env/src/env.rs 的 uu_app（约第125–200行）；Options 结构体和 make_options（约第482行）要一并带上新选项的值，才能传到 run_program。
2. 信号要在 run_program（约第380行）里、cmd.status() 之前生效，让子进程继承“忽略”的处置。env 自己进程的处置（ignore_interrupts、sigaction）要分清楚改的是谁。
3. env.md 的帮助文本和 usage 要核对；Cargo.toml 里 nix 的 features 是否够用。
4. -S/--split-string 是自己实现的解析（parse_args_from_str、split_iterator.rs），检查 -S 展开出的参数里带 --ignore-signal 时能否识别。

B. 题面没给例子、但很可能被检查的输入/边界情况
1. 不带值的 --ignore-signal（[=SIG]）表示忽略所有信号；SIGKILL、SIGSTOP 不能被忽略，遇到时不能报错或崩溃。
2. 带值的写法：名字（INT、SIGINT）、数字、逗号分隔列表、重复多次。
3. 非法信号名或数字要有明确报错和退出码；核对 signal_by_name_or_value 的解析规则（大小写、SIG 前缀、0）。
4. 值可选（num_args 0..1）：--ignore-signal INT 空格写法不能把 INT 当成程序名。
5. 与 --debug 同用时是否要打印信息，参考已有 debug 输出格式。

C. 仓库里已有的约定、文档或测试
1. uucore 的 signals.rs 已有信号转换函数和 ALL_SIGNALS，应复用。
2. env.rs 中子进程被信号终止后的处理逻辑（约第430–455行）。
3. tests/by-util/test_env.rs 里 --argv0、-S、--debug 的测试写法和 cfg(unix) 限制。
4. 非 unix 平台的处理可参考 --argv0 的 cfg 分支和报错。

D. 建议提交前额外自测的情况
1. env --ignore-signal=INT sh -c 'kill -INT $$; echo alive' 应输出 alive，不加选项时进程被终止。
2. 不带值、逗号列表、重复选项、非法信号名各跑一次，核对退出码和报错。
3. 选项放在命令名前后各试一次，确认之后的参数原样传给程序；再用 -S 写法试一次。
