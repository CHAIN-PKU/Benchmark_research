**档案：echo 后接 @verbatim 的换行问题**

**【1 题面要点】**
- 期望行为：`{{ 1 }}` 后面紧跟 `@verbatim` 时，输出的换行数要和普通情况一致。题面原话是"zero or two newlines are echoed. It does not seem possible to echo one newline."
- 复现给了两组输入输出。
  - 输入 1：`{{ 1 }}@verbatim\nsecond line\n@endverbatim`。实际输出 `1second line`，echo 与 verbatim 内容之间 0 个换行。
  - 输入 2：`{{ 1 }}\n@verbatim\n...`。实际输出 `1\n\nsecond line`，中间 2 个换行。
- 题面没有给期望输出的原文，也没有给修法建议。
- 隐含的期望：输入 1 应为 `1\nsecond line`（verbatim 开头的换行保留），输入 2 应为 `1\n\nsecond line`。换行数要与 `{{ 1 }}` 后接普通文本时一致。

**【2 相关代码】**
- `src/Illuminate/View/Compilers/BladeCompiler.php:257` `compileString`：整体流程如下。
  - 第 265 行先调用 `storeUncompiledBlocks`，把 verbatim/php 块换成占位符。
  - 第 281 行 `token_get_all` 解析。
  - 第 285-287 行调用 `restoreRawContent` 还原占位符。
- `BladeCompiler.php:391` `storeVerbatimBlocks`：正则 `/(?<!@)@verbatim(.*?)@endverbatim/s`，把 `$matches[1]` 原样存为原始块。块内容以 `\n` 开头。
- `BladeCompiler.php:417` `storeRawBlock` 和 `:464` `getRawPlaceholder`：占位符是 `@__raw_block_#__@`。
- `BladeCompiler.php:447` `restoreRawContent`：用 `preg_replace_callback` 还原占位符，是还原时机和位置的候选改动点。
- `src/Illuminate/View/Compilers/Concerns/CompilesEchos.php:68/89/110`：`compileRawEchos`、`compileRegularEchos`、`compileEscapedEchos`。
  - 正则末尾 `(\r?\n)?` 捕获 echo 后的换行。
  - 第 73/94/115 行 `$whitespace = empty($matches[3]) ? '' : $matches[3].$matches[3];`，把捕获到的换行重复一次，用来抵消 PHP 的 `?>` 吞掉紧随其后一个换行的行为。

**根因（我的推断，未运行验证）**：echo 编译在占位符替换之后、还原之前。
- 输入 1：echo 后面是占位符，没有 `\n`，不补换行。还原后变成 `?>\nsecond line`，运行时 PHP 吞掉这个 `\n`，输出 0 个换行。
- 输入 2：echo 后的 `\n` 被加倍成 `\n\n`，再加上 verbatim 内容开头的 `\n`，共 3 个。PHP 吞掉 1 个，输出 2 个。

**【3 并列与牵连】**
- 三个 echo 方法有相同的 `$whitespace` 逻辑，且模式相同。如果改 echo 侧，要同时改三处。
- `@php ... @endphp` 也走同一套 `storeRawBlock`（`BladeCompiler.php:404-409`）。内容是 `<?php...?>`，开头不是换行，但它同样可能紧跟在 echo 之后，需确认不被改坏。
- 如果改在 `restoreRawContent` 或 `storeVerbatimBlocks`，会影响所有 verbatim 和 php 块的输出。
- `@verbatim` 前后的其他指令（如 `@if` 后接 verbatim）也可能受影响。
- 还有 `ltrim($result, "\n")`（`BladeCompiler.php:477`）：只作用于 footer。

**【4 现有测试与约定】**
- `tests/View/Blade/BladeEchoTest.php:21-24`：断言 `"{{ \$name }}\n"` 编译为 `"<?php echo e(\$name); ?>\n\n"`，`\r\n` 同理。这是换行加倍的既有约定，不能破坏。
- `tests/View/Blade/BladeVerbatimTest.php:14-31`：`'Some text\n@verbatim\n    {{ $a }}...@endverbatim'` 的期望是 `'Some text\n\n    {{ $a }}...\n'`。verbatim 开头的换行原样保留，不改。
- `BladeVerbatimTest.php:49-80`：断言 `<?php echo e($first); ?>\n\n<?php\n    echo $second;...`，以及 `@include("users")...?>\n\n    {{ $fourth }}`。其中 `@include` 之后紧跟 verbatim 块，编译结果里 `?>` 后有额外的空行。这个测试说明指令后接 verbatim 的"加一个换行"约定已存在，新逻辑要与它一致。
- `BladeVerbatimTest.php:33-38`：`@endverbatim {{ $b }} @verbatim`，echo 前后都是空格，不涉及换行。
- 外部规范：PHP 的 `?>` 会吞掉紧随其后的单个换行，这是正确行为的依据。
- 与题面不冲突，但新测试要同时满足上述既有断言。

**【5 边界与隐含要求】**
- `\r\n` 换行：echo 正则已支持 `\r?\n`，verbatim 内容开头也可能是 `\r\n`。
- 三种 echo 都要覆盖：`{{ }}`、`{!! !!}`、`{{{ }}}`/escaped。
- verbatim 内容开头没有换行的情形，例如 `{{ 1 }}@verbatim text`。此时输出紧贴，不应误加换行。
- 空 verbatim 块和 verbatim 紧跟 `@endverbatim` 的情形。
- 多个相邻 raw 块，以及 `@php` 块紧跟在 echo 后。
- 不能破坏 `@{{ }}`（转义）分支，该分支原样返回 `substr($matches[0], 1)`。
- 不能破坏上面第 4 节列出的既有断言。
- 修复位置的选择：改 echo 是把占位符视为"后接换行"；改 verbatim 是让占位符自带补偿。两种方式对 `@php` 的影响不同。

**【6 改动规模】**
- 预计 1-2 个文件。主要是 `BladeCompiler.php`，可能是 `storeVerbatimBlocks`、`restoreRawContent` 或 `storeRawBlock` 里加一小段逻辑。如果改 echo 侧，则还要改 `CompilesEchos.php` 的三处。
- 属于局部修补，不需要新增结构。
- 测试需新增在 `BladeVerbatimTest.php`。

**【7 难点一句话】**
难点在于看懂换行加倍是为了抵消 PHP 的 `?>` 吞换行，而占位符机制让 echo 看不到后面的 verbatim 内容，所以要在不破坏既有 echo 和 verbatim 换行断言的前提下，选对修复位置。