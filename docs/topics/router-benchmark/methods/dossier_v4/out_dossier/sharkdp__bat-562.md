# 仓库档案：bat 中 `bat c`/`ca`/`cac`/`cach` 被当成 cache 子命令

## 【1 题面要点】
- 期望行为：`bat c`、`ca`、`cac`、`cach` 应当作为普通文件名处理。题面称现状有两种结果：
  1. 当前目录存在名为 `cache` 的文件时，会错误地打印该文件。
  2. 否则报错，提示需要 `--build`/`--clear`。
- 原因：题面指出"clap parser doesn't require an exact match: any prefix of the subcommand 'cache' will do"。
- 题面没有给复现命令和期望输出。
- 修法建议只有一句："I think it's best to avoid subcommands and use something like `--cache` instead."
- 题面提到 #245（文件名 "cache" 问题）和 #275（对应的修复），即现有的 `Path::new("cache").exists()` 变通方案。
- 题面没有说明 flag 的具体写法。从"avoid subcommands"和 `--cache` 推断，大概是 `bat --cache --build/--clear`。

## 【2 相关代码】
- `src/clap_app.rs:1-14`：
  - `build_app` 中用 `arg_group_required = !Path::new("cache").exists()`（约 L11-12）做 #275 的变通。
  - L18 的 `.setting(AppSettings::InferSubcommands)` 是前缀匹配的根源。
  - L19 的 `ArgsNegateSubcommands`，L21 的 `VersionlessSubcommands` 也都是子命令相关设置。
- `src/clap_app.rs:~370-420`：`.subcommand(SubCommand::with_name("cache")...)`，子命令里有 `build`(-b)、`clear`(-c)、`source`、`target`、`blank` 这几个参数，另有 `ArgGroup "cache-actions"`，其 `required(arg_group_required)`。其中 `source`/`target`/`blank` 通过 `.requires("build")` 依赖 build。
- `src/clap_app.rs` 中已有隐藏的顶层选项 `cache-dir`、`config-dir`、`config-file`（`.hidden(true)`），可作为新增顶层 flag 的写法参考。
- `src/app.rs:111-132`：`App::matches` 里 `wild::args_os().nth(1) == Some("cache".into())` 时跳过配置文件参数。这一处用的是精确字符串比较，改成 flag 后要同步改判断。
- `src/main.rs:85-100`：`run_cache_subcommand(matches)` 读取 `build/source/target/blank/clear`。
- `src/main.rs:198-215`：`run()` 里 `match app.matches.subcommand() { ("cache", Some(cache_matches)) => ... }`。这里有 #275 的补丁：参数为空时把 `InputFile::Ordinary(&"cache")` 当文件打开。
- `src/main.rs:216-236`：`_` 分支依次处理 list-languages、list-themes、config-file、config-dir、cache-dir，最后 `run_controller`。

## 【3 并列与牵连】
- 并列实现：`App::matches`（app.rs）和 `run()`（main.rs）都对 "cache" 做了特殊处理，clap_app.rs 里还有一处，共三处，需要同步修改。
- 改成 flag 后，#275 的补丁（`Path::new("cache").exists()`、空参数时回退打开文件 "cache"、`use std::path::Path` 的导入）都应删除。它们本来就是为子命令方案服务的。
- 文档和脚本里调用 `bat cache --build/--clear` 的地方：
  - `README.md:329,337,353`
  - `doc/README-ja.md:277,284,300`
  - `assets/README.md:16,28`
  - `assets/create.sh:7,15`（会实际执行）
- `doc/bat.1:138-141` 有 "SUBCOMMANDS / cache" 一节。
- `assets/completions/bat.fish`：
  - 约 L5-53 各行有 `-n "not __fish_seen_subcommand_from cache"`。
  - L55-60 是 cache 子命令补全。
  - build.rs 中补全生成目前已被注释掉。
- CI 脚本 `.travis.yml`/`appveyor.yml` 中的 "cache" 是 CI 缓存，与此无关。
- 未发现 CHANGELOG 文件。

## 【4 现有测试与约定】
- `tests/integration_tests.rs` 里没有任何与 cache 相关的测试（grep "cache" 在 tests/*.rs 无匹配）。
- 测试的写法：`bat()` 辅助函数（L30）= `bat_with_config()` + `--no-config`，cwd 为 `tests/examples`。典型断言如 `bat().arg("test.txt").assert().success().stdout("hello world\n").stderr("")`（L37-44）。
- 隐藏测试大概率是在 `tests/examples` 下放一个名为 `cache` 的文件，再断言 `bat cache`/`bat c` 之类输出该文件内容。也可能放 `c`、`ca` 等文件，同时可能断言 `bat --cache --build` 可用。
- 外部约定：`bat cache --build` 在 README 里有文档说明，这是旧接口。题面要求改成 flag 后，两者冲突需要更新。
- 隐藏测试能否过，取决于 `bat cache` 作为文件名是否被正确处理。
- `tests/examples` 目录下当前没有 `cache` 文件（ls 结果里没有）。
- 现有 `bat_with_config()` 会读配置文件。要是改成 flag，`app.rs` 里"跳过配置文件"的判断可能影响测试（与 `--no-config` 无关，但与 `--cache` 的位置判断有关）。

## 【5 边界与隐含要求】
- 去掉子命令后要同时删除 `InferSubcommands`、`ArgsNegateSubcommands`、`VersionlessSubcommands`、`DisableHelpSubcommand`。若只删 subcommand 定义而保留 setting，行为可能出岔子（有的设置对无子命令的 app 无效，需要核实）。
- 新 flag 的参数依赖：`--build`/`--clear` 要求 `--cache` 才有意义，`--source/--target/--blank` 要求 `--build`。要用 clap 的 `requires`/`conflicts_with`，否则 `--cache` 不带动作会静默无事发生。
- clap 2 的长选项同样支持前缀推断吗？默认 clap 2 不推断长选项，需要核实（`InferSubcommands` 只针对子命令，题面没有谈长选项）。
- 短选项冲突：`-b`/`-c` 当前是子命令内的短选项，挪到顶层要避免与现有顶层短选项冲突（现有有 `-l -m -p -n -A -r -H -u`，`-c` 与 `-b` 目前未被占用）。
- `--cache` 本身是一个顶层选项，与现有的 `--cache-dir` 有前缀关系，需要确认 clap 2 在无推断时不会混淆（`--cache` 应精确匹配）。
- 配置文件：原先 `bat cache` 时跳过配置文件，现在改为 flag 后，要决定是否仍跳过（例如 config 里 `--style=...` 会与 cache 构建冲突吗？一般不会）。
- 帮助文本 `--help` 的输出，以及 `bat.1` 的 man page 里 SUBCOMMANDS 一节。
- 与 `--list-themes`、`--list-languages` 的冲突：`config-file` 用了 `conflicts_with`，可以参考。
- main.rs 里的优先级：`cache` 分支要放在 `_` 分支里，且不能被 `list-languages` 等抢先。

## 【6 改动规模】
- 源码：3 个文件（`clap_app.rs`、`main.rs`、`app.rs`），合计约 4-6 处。主要是在 clap 里把子命令改成顶层 flags，以及调整 main 的分派逻辑。
- 文档/脚本：README.md（3 处）、doc/README-ja.md（3 处）、assets/README.md（2 处）、assets/create.sh（2 处）、doc/bat.1、bat.fish，共约 6 个文件。其中隐藏测试可能间接依赖的只有 `create.sh`。
- 属于局部重构：不需要新结构，也不贯穿多层。核心难度较低，但要改的地方分散。

## 【7 难点一句话】
难点不在逻辑本身，而在于把分散在三个文件里的"cache 子命令"特判（clap 设置、`app.rs` 的精确字符串判断、`main.rs` 的 #275 回退）一次改干净，并确认 clap 2 去掉子命令后 `c`/`ca` 等能作为普通文件名通过。同时要想清楚新 flag 的命名与依赖关系，因为题面只说"something like `--cache`"，没有给出确切接口，而隐藏测试可能依赖具体写法。