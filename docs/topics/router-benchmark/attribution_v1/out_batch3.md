# 批次3 挂因分析（DS 两次尝试，4 题）

## 1. google__gson-2061（run1 过，run2 挂）
1. 题目要什么：JsonReader.hasNext() 在读到文档末尾（peek() == END_DOCUMENT）时不该返回 true。
2. 标准答案：两处各改一行。stream/JsonReader.java 的 hasNext 多排除 PEEKED_EOF；internal/bind/JsonTreeReader.java（另一个子类实现，自己重写了 hasNext）多排除 JsonToken.END_DOCUMENT。
3. DS 两次：
   - run1（过）：两个文件都改，和标准答案逐字等价，还补了两个测试，跑了全量 mvn（1084 个全过）。
   - run2（挂）：只改了 JsonReader.java，完全没碰 JsonTreeReader.java；只跑了 JsonReaderTest。
   - 挂在：JsonTreeReaderTest#testHasNext_endOfDocument。
4. 挂因：漏改某处（同一行为有两个实现类）。run2 的最终说明只提到 JsonReader，没有搜 hasNext 的其他实现/重写；也没有跑整个模块的测试（run1 跑了全量，所以发现并顺手改了 TreeReader）。题面只写 JsonReader.hasNext()，没提 JsonTreeReader，属于"题面窄、正确修法要覆盖兄弟实现"。证据：run2 diff 只含 stream/JsonReader.java；失败测试在 JsonTreeReaderTest。
5. 类别：C 主（跨文件/多实现要同步改）；副 A（题面场景窄）。
6. 动手前可见信号：题面本身只说 JsonReader，但仓库里 `grep "boolean hasNext"` 会看到 JsonTreeReader 继承 JsonReader 且重写了 hasNext，同一语义有两份实现，同一个类 API 的修复通常要在所有重写处同步。另外，题面极短，测试验证范围需要自己想到（只改一处、只跑一个测试类就停手是风险点）。若只看题面不看仓库则看不出。
7. 把握：高。

## 2. jordansissel__fpm-1829（run1 过，run2 挂）
1. 题目要什么：Debian 打包时，versioned Provides（带版本的 provides）只允许 `=`，用 `<<` 等其他关系应在构建时报错（FPM::InvalidPackageConfiguration）。
2. 标准答案：在 deb.rb 加一个完整的 relationship 字段正则（RELATIONSHIP_FIELD_PATTERN，含名字、括号、关系符、版本格式），output 里对每个 provides 调用 valid_provides_field?，不匹配（格式不合法）或关系符不是 `=` 都抛 InvalidPackageConfiguration。即"整串格式校验"，不只是比较运算符。
3. DS 两次：
   - run1（过）：在 fix_provides 里 `provides.scan(/\(([^)]+)\)/)` 取括号内内容，取第一个词作为运算符，不是 "=" 就抛错。因此 "(>)"（括号里只有运算符，无版本）也被拦下。
   - run2（挂）：用正则 `/\(\s*([<>=]+)\s*[^)]+\)/`（要求运算符后至少还有一个非 `)` 字符）或裸写形式匹配，抓到 `<<`；但 "hello (>)" 没有版本号，正则匹配不上，不抛错。
   - 挂在：should reject 'hello (>)'（F2P 之一）。`<<` 那条两次都过。
4. 挂因：改法不够通用——只针对题面例子（带完整版本号的非 = 运算符）写了匹配，没覆盖"运算符后缺版本"这类畸形输入。证据：run2 diff 的正则 `[^)]+` 要求版本非空；测试 invalid 列表含 "hello (>)"、"hello ()"、"hello (1234)"、"hello = world"。另外 run2 最终说明称 spec 里 24 个用例因 File.exists?（新 Ruby 已移除）在 deb.rb:545 失败，被它当作"无关的既有失败"，没有真正跑新 reject 用例；run1 的测试输出里同样有 3 个 reject 用例 failed，但它们不在 F2P/P2P 里，不计分。
5. 类别：A 主（题面场景窄、要更通用）；副 E（题面标题"invalid version strings"比正文宽，隐藏测试要求整串格式校验，含畸形串）。
6. 动手前可见信号：题面标题是"allows invalid version strings"（无效版本串），而正文例子只有 `<<`；标题比例子宽，提示校验不止"运算符是否为 ="。另外 fix_provides 里已有基于正则的语法规整（`name = version` → `name (= version)`），说明仓库有"字符串形态"处理，容易预期要对整串形态做校验。这些线索较弱，只能说"需要自己想到 `(>)`、`()` 这类畸形输入"。基本属于隐约可见。
7. 把握：中高（F2P 里的 "hello (>)" 与 run2 正则缺口一一对应，证据直接；但"题面是否提示畸形串"带主观判断）。

## 3. jqlang__jq-2728（run1 挂，run2 过）
1. 题目要什么：jq 支持 NO_COLOR 环境变量（见 no-color.org），用来在没有 tty 检测可用时关闭彩色输出。
2. 标准答案：main.c 里只在"颜色是由 tty 自动检测打开的"那段里检查 NO_COLOR（非空才生效）并关掉颜色；因为在 -C 处理之前，所以显式 `-C` 仍然强制彩色。隐藏测试 tests/shtest 用 `script` 伪终端验证四种情况：未设、NO_COLOR 为空、NO_COLOR=1（无色）、NO_COLOR=1 且 `-C`（仍有色）。
3. DS 两次：
   - run1（挂）：把 NO_COLOR 检查放在 `-C`/`-M` 处理之后，所以 NO_COLOR=1 连 `-C` 也被压掉；它自己的测试也写成"NO_COLOR=1 jq -Ccn → 无色"，等于把错误优先级写进了测试，并以此自证通过。
   - run2（过）：把检查放在 `-C` 之前，`-C` 优先；并顺手更新了手册和 jq.1.prebuilt，其最终说明明确写了"NO_COLOR=1 jq -C → 彩色（-C 显式请求优先）"。
   - 挂在：tests/shtest（整体一个测试；输出里 8 个里 1 个 FAIL）。
4. 挂因：理解偏差——NO_COLOR 与显式 `-C` 的优先级弄反。题面未说明优先级，no-color.org 规范里"用户显式配置/命令行可覆盖"才是通行约定；run1 没有想到这点，还把自己的假设写进测试。证据：run1 patch 位置在 `if (options & NO_COLOR_OUTPUT)` 之后；hidden test 的 `NO_COLOR=1 faketty $JQ -Cn .` 期望 `\033[1;30mnull\033[0m`。
5. 类别：E 主（隐藏要求：优先级，题面没写）；副 B（要遵守"显式 flag 覆盖环境变量默认"的约定）。
6. 动手前可见信号：题面提到"-M 能关颜色，但想用 NO_COLOR"，没提 -C 怎么办；jq 手册里 -C 的描述是"force"（强制），说明 -C 语义上就是最高优先级；no-color.org 页面也写明环境变量只是默认值、命令行可覆盖。会读规范+手册的 agent 能推出来，但题面本身看不出。较弱信号：行为是个"多个来源冲突时谁优先"的设计题，题面没有给规则。
7. 把握：高（两次差别只在一行放置位置，证据清楚）。

## 4. preactjs__preact-4436（run1 过，run2 挂）
1. 题目要什么：函数式 ref（callback ref）可返回一个清理函数，元素卸载或 ref 变化时调用它（类似 React 19），且有清理函数时不再用 null 调用 ref。
2. 标准答案：只改 src/diff/index.js 的 applyRef：把返回的清理函数存在 ref 函数对象自身的 `_unmount` 上；下次调用先执行旧清理；有清理函数且 value 为空时不再调用 ref(null)；另外改了 internal.d.ts 的类型。不动 diffChildren/unmount。
3. DS 两次：
   - run1（过，92 轮）：同样在 applyRef 里把清理函数存在 `ref._cleanup`（挂在 ref 函数上，和标准做法同思路），value 为空且有清理函数时调用清理；改类型。没动 diffChildren。
   - run2（挂，103 轮）：把清理函数存在 `vnode._refCleanup`（还改了 mangle.json），并改了 diffChildren（去掉 `childVNode.ref &&` 判断，旧 ref 对 oldVNode 做 detach，ref 未变时把 _refCleanup 搬到新 vnode）和 unmount 的 applyRef 参数。
   - 挂在：F2P 两个新测试都过，但老测试 P2P 中的 refs > should first clean-up refs and after apply them 失败，实际输出多出一个 "removing ref from three"（期望 4 条，得到 5 条）。
4. 挂因：改坏老测试（副作用）。run2 把存储位置放到 vnode 上，不得不改 diffChildren 的条件（去掉 `childVNode.ref &&` 前置，扩大了触发 null 回调的情形），改变了老的 ref 卸载/重挂顺序。推断依据：失败只出现在"移除 ref"相关的已有顺序测试，多出的一次 ref(null) 调用来自 diffChildren 的改动，这点是根据 diff 与断言差异推断的，未跑仓库验证。另外 run2 称 Karma 浏览器测试在沙箱里跑不起来，只用 Node + 自写 DOM shim 验证，没有跑到仓库已有的 refs 测试，因此没发现回归（run1 的 Karma 能跑，26 个全过）。
5. 类别：D 主（修好了新功能，改坏老测试）；副 F（run2 环境里测试执行失败，没有用真实测试回归）、副 C（改多处引入风险）。
6. 动手前可见信号：改动落在 diff 引擎核心，refs.test.js 里已有"ref 先清理后应用的顺序""memoized 组件 ref 置 null"等多个顺序敏感的测试，一眼可知 ref 生命周期很脆弱；因此"最小改动（只动 applyRef）"优于"改 diffChildren"。题面只描述功能，看不出具体陷阱，但只要读到 refs.test.js 里这批顺序测试就能预判需要小改动并跑回归。题面本身：看不出。
7. 把握：中（失败测试和 diff 对应关系是推断的，具体哪行引起多余 ref(null) 未经运行确认；run2 环境无法跑 Karma 是确证的）。
