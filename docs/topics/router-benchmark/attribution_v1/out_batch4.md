# DS 挂因分析 batch4（4 题）

## 1. rubocop__rubocop-13396（Style/RedundantParentheses）

1. 题目要什么：`render json: (xxx.map do ... end.to_h.camelize)` 里的括号其实不能删（do...end 块会绑到外层无括号的方法调用上），cop（RuboCop 的一条检查规则）却误报并自动改坏了代码。要求不再误报。
2. 标准答案：新增 `do_end_block_in_method_chain?`：括号内任意后代有 `do...end` 块（`block.keywords?`），且括号节点有任一 send/csend 祖先，就不报。同时删掉旧的 `allowed_method_call?` / `arg_in_call_with_block?`，并把 `{}` 块的 `lambda`/`proc` 场景改成报 offense（隐藏测试里新增了这类用例）。
3. DS 两次：
   - run1 通过（resolved=true，94 轮）：新增 `allowed_do_end_block?`，向上找“把该节点当参数的调用”，用 `call_node?` 同时认 `send / csend / super / yield`，外层无括号才放行。
   - run2 失败（62 轮）：新增 `block_binding_would_change?`，沿祖先走，`case ancestor.type when :send, :super`，漏了 `:csend`（安全导航 `&.`）。挂在 F2P `...do...end block in keyword argument for safe navigation call` 与对应 `numblock ... for safe navigation call` 两个测试。老测试没坏。
   两次差别：run1 把 csend 算进调用类型，run2 没有。
4. 挂因（run2）：漏改某一类节点——`&.` 调用（csend）没当作“外层调用”。证据：run2 代码 `when :send, :super`，失败测试名里都带 safe navigation。属于“改法不够通用/漏分支”，不是理解偏差（主场景 `render json:` 已经通过）。
5. 类别：A（正确修法要覆盖更多语法变体）为主；副 C（要同时覆盖 send/csend/block/numblock 多个节点类型）。
6. 动手前可见信号：RuboCop 的 AST 里“方法调用”有 send 与 csend 两个类型，仓库里同一 cop 的别处代码（如 `check_send` 和 `each_ancestor(:send, :csend)` 风格）经常成对出现；题面只有一个 `render` 例子，看不出 `&.`。只看题面几乎看不出，但“仓库里 cop 逻辑通常 send/csend/numblock 成对处理”是一个可事先提醒的通用线索。run1 能过说明 DS 本来就有能力，这题偏随机（一过一挂）。
7. 把握：高（失败测试名与代码一一对应）。

## 2. rubocop__rubocop-13560（Style/FileNull）

1. 题目要什么：`foo('nul')` 里的小写 `'nul'` 被误当成 `File::NULL`（空设备）报了 offense，用户希望忽略 `'nul'`。
2. 标准答案：并没有简单去掉 `nul`，而是加规则“只有文件里出现了 `'/dev/null'` 字符串时，才把 `nul`（大小写不敏感）当空设备报”；`NUL:` 仍始终报。实现是 `on_new_investigation` 先扫描整个文件有没有 `/dev/null`，`on_str` 里 `nul` 且文件无 `/dev/null` 就跳过。同时保留不区分大小写。
3. DS 两次几乎相同（都失败，20 轮 / 17 轮，且很快）：删掉正则的 `i` 标志（`%r{\A(/dev/null|NUL:?)\z}`），使 `nul`、`/DEV/NULL` 都不再报；并把原有的 `is case insensitive` 测试改掉/删掉（改成“不报”）。挂在 F2P `does not register an offense when the entire string is 'NUL' without '/dev/null'`（大写 `'NUL'` 单独出现也应不报，DS 仍报）和 P2P `is case insensitive`（DS 改变了既有行为）。
4. 挂因：理解偏差 + 改坏老测试。题面只说“忽略 `'nul'`”，DS 取了最小改法“去掉大小写不敏感”，并且自己改写了仓库里已有的 `is case insensitive` 测试来迁就自己的改法（证据：patch 里把该测试替换），而不是保留它。标准答案要求的“靠文件内是否有 `/dev/null` 做上下文判断”在题面里完全没有提示，属于隐藏的设计选择。
5. 类别：E（题面信息不足，正确解是维护者取舍的上下文规则）为主；副 D（改坏并改写了老测试 `is case insensitive`）。
6. 动手前可见信号：有一个很具体的信号——仓库里已有测试 `is case insensitive` 明确要求 `"nul"` 和 `"/DEV/NULL"` 被报。题面要求“忽略 `'nul'`”恰与这条既有测试冲突；DS 一旦想删/改一个现有测试来让自己通过，就说明走偏了。另外题面是 issue 里的“是否应该”提问口吻（Expected 只有一句“Ignore 'nul' strings”），修法有多种取舍，没有唯一正确答案。可事先判断为“规格有多种合理解、需维护者取舍”。
7. 把握：高（两次 patch 同构，失败测试与代码对应）。

## 3. sharkdp__bat-2650

1. 题目要什么：`--map-syntax='*.config:XML'` 对 `NuGet.Config` 不生效（大小写敏感），希望不区分大小写。题面是 Windows 用户报告。
2. 标准答案：一行改动，`src/syntax_mapping.rs` 的 `GlobBuilder::new(from).case_insensitive(false)` 改成 `true`（并加 CHANGELOG）。
3. DS 两次：
   - run1 通过（21 轮）：同样改成 `case_insensitive(true)`，另加单元测试。
   - run2 失败（35 轮）：改成 `case_insensitive(cfg!(windows))`，即只在 Windows 编译时才不区分大小写。测试环境是 Linux，所以隐藏的集成测试 `highlighting_independant_from_map_syntax_case`（`--map-syntax=*.Config:JSON` 对 `.Config` 文件应与 `*.config` 输出一致）在 Linux 上仍然失败。
4. 挂因：理解偏差——DS 把标题里的“on Windows”当成限定条件，只修了 Windows。证据：patch 里注释 “File systems are case-insensitive on Windows”，以及 `cfg!(windows)`；而题面正文里“What did you expect”写的是“使用扩展名大小写不全小写时也应着色”，没有说只限 Windows。run2 自己只在 Linux 跑了 `cargo test --lib`，没有验证新行为在测试平台上是否生效（该改动在 Linux 上等于没改）。
5. 类别：A（题面场景窄——标题写 Windows，但正确修法是全平台通用）。副：F 不是；副 G：没有在当前平台验证修复是否真起作用。
6. 动手前可见信号：标题“seems to be case sensitive on Windows”会诱导平台条件修法；但仓库里 bat 的内置扩展名检测本来就是跨平台大小写不敏感（run1 就引用了 `syntax_detection_is_case_insensitive` 测试），说明 bat 的设计取向是全平台一致。另一个自检线索：任何 `cfg!(windows)` 只在 Windows 生效的修复，在 Linux 测试环境里没法被验证。可预示“有平台条件陷阱”，但 run1 说明 DS 通常能走对，偏随机。
7. 把握：高。

## 4. uutils__coreutils-6377（env --ignore-signal）

1. 题目要什么：给 Rust 版 `env` 实现 `--ignore-signal[=SIG]`，让指定信号（SIGINT 等）被忽略。题面只有 GNU 手册一行描述。
2. 标准答案：`env` 进程自己先对每个信号调用 `signal(sig, SigIgn)`（`apply_ignore_signal`），再 spawn/exec 子进程，让忽略状态被继承；选项是 `ArgAction::Append` 的 os_string，不加 `require_equals`；逗号分隔多个信号；错误信息固定格式：非法信号 `env: 'banana': invalid signal`（退出码 125）；SIGSTOP/SIGKILL 报 `env: failed to set signal action for signal N: Invalid argument`（125）；空值 `--ignore-signal=` 成功。
3. DS 两次（都失败，且都 `gate: uncertain`）：
   - run1（89 轮）：用 `Command::pre_exec`（子进程 exec 前）安装 `SIG_IGN`，`num_args(0..=1)` + `require_equals`；非法信号用 `UUsageError`，信息 `'FOO': invalid signal`，退出码 125。挂在 `test_env_arg_ignore_signal_valid_signals`（断言 `target.is_alive()` 失败，test_env.rs:854）。
   - run2（73 轮）：同样 `pre_exec`；非法信号信息写成 `invalid signal 'banana'`（顺序与格式不对）。挂在 `..._invalid_signals`（期望包含 `env: 'banana': invalid signal`，实际 `env: invalid signal 'banana'`）和 `..._valid_signals`（同样 854 行 is_alive）。
4. 挂因：
   - 两次共同：valid_signals 测试是对 **env 进程本身**发 SIGINT（`child.id()` 是 env 的 pid，env 后面再运行 `sleep 1000`），期望 env 进程不死。DS 为避免“ignore SIGCHLD 导致 env 等不到子进程”，刻意只在子进程 pre_exec 里设置忽略，env 自己没忽略，所以 SIGINT 把 env 杀掉了。证据：失败行 `assertion failed: target.is_alive()`，且两份 final message 都明说“避免在 env 父进程中忽略 SIGCHLD”。这是对语义的另一种合理理解（GNU 行为是对子命令忽略），与实际测试观察点（env 进程本身）不一致，属于隐藏要求。
   - run2 额外：错误信息格式不对，没去参照 GNU/本仓库已有的 `'xxx': invalid signal` 写法（run1 找到了正确格式）。属于“精确输出格式”。
5. 类别：E（测试观察 env 进程自身，题面未说明）为主；副 B（错误信息必须与 GNU/仓库格式精确一致，run2 中招）。
6. 动手前可见信号：题面只有一行 man 手册，没有说明行为、错误信息、退出码，纯“照 GNU env 实现新选项”类。可预见的难点：(a) 错误信息和退出码要与 GNU 完全一致，需要对照 GNU `env` 实际输出，仓库里同文件其他选项（如 `-u`、`-C`、`-S`）的错误措辞可作参考；(b) 信号语义（谁忽略、何时忽略）有多种实现，且新增大型功能（解析、多信号、逗号分隔、特殊信号）有多个行为点，隐藏测试很可能覆盖全部。所以“新功能、规格只有一行、且需精确文本”是对 DS 难度高的预警；具体 env 自身要先忽略信号这点只看题面看不出。
7. 把握：高（失败行与源码对应）；对“env 自身 vs 子进程”这一因果是中高——基于测试的 `child.id()` 与 DS 的 pre_exec 实现推断，未在容器里重跑验证。
