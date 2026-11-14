# 第二批归因（caddy-6345 / fmt-3750 / gin-1957 / gson-1100）

## 1. caddyserver__caddy-6345（run1 过 / run2 挂）
1. 题目要什么：让 JSON 配置里的 `sign_with_root` 选项能在 Caddyfile 里写。题面只给了一个指向 internal issuer（内部签发器）JSON 文档的链接。
2. 标准答案：只改 `modules/caddypki/acmeserver/caddyfile.go`，在 `parseACMEServer` 里新增 `sign_with_root` 分支（无参数，置 `acmeServer.SignWithRoot = true`）。也就是加在 `acme_server` 指令里，不是 `tls` 指令里。测试是新 caddyfiletest：`acme_server { ca internal; sign_with_root }`。
3. DS 两次：
   - run1：改的就是 `acmeserver/caddyfile.go`，加了同样的分支，过。最终消息说它先查到 internal issuer 的 Caddyfile 解析器早已支持 `sign_with_root`，缺口只在 `acme_server`。
   - run2：改了 `caddyconfig/httpcaddyfile/builtins.go` 的 `parseTLS`，给 `tls internal { ... }` 加了 `sign_with_root`、`lifetime`，还把 `ca` 子指令改成"internal 时设 InternalIssuer.CA"。完全没碰 `acme_server`。挂在 `TestCaddyfileAdaptToJSON`，因为新增的 `acme_server_sign_with_root` 用例里 `acme_server` 不认 `sign_with_root`。
4. 挂因：理解偏差，不是实现能力。run2 照题面链接（internal issuer）去改，把需求当成"tls internal 要支持"，没有先确认 `sign_with_root` 在 Caddyfile 里到底哪里缺。run2 还顺手扩了 `lifetime` 和改了 `ca` 的既有行为（超范围）。自测只验证了自己写的 `tls internal` 用法，所以"测试通过"是假信号。
5. 类别：E（题面信息不足，指向的位置有歧义）为主；副类 G（DS 没核实缺口就动手）。
6. 动手前可见信号：有。题面的链接指向 `issuers/internal`，但仓库里 `sign_with_root` 在 internal issuer 的 Caddyfile 解析器 `internalissuer.go` 里已经有了。用 grep 一下 `sign_with_root` 就能看出：JSON 里有它的结构体不止一个（`InternalIssuer.SignWithRoot` 与 `acmeserver.Handler.SignWithRoot`），其中只有 acme_server 那个没有 Caddyfile 对应。所以题面的"链接 + 一句话需求"与仓库现状不符，是个歧义点；该题难点是"先找出真正缺的是哪一个"。run1 就是这样找到的。
7. 把握：高（两次 diff 与测试输出直接对应）。

## 2. fmtlib__fmt-3750（两次都挂，同一原因）
1. 题目要什么：`{:LX}`（带本地化 L 的十六进制）输出成了十进制，要求 L 与 x/X/o/b 等进制类型能同时生效。
2. 标准答案：重写带数字分组的 `write_int`（digit_grouping 版本）：按 `specs.type` 分支，用 `format_uint<4/1/3>` 生成十六/二/八进制数字到 buffer，处理 `#` 前缀（`prefix_append` 上移并支持多字符前缀）、八进制前缀规则、`c` 类型，然后对数字串做分组（千位分隔符）并按宽度填充。测试 `format_locale` 期望 `"7,5bc,d15"`、`"-0b111,010,..."`、`"    30,071"`：即非十进制也要加分隔符。
3. DS 两次几乎一样：在 `loc_writer::operator()` 里，若 `specs.type` 不是 none/dec 就 `return false`，回退到非本地化的 `write_int`。输出变成 `75BCD15`（与 std::format 一致）。run2 另外在 `format_int_locale` 里加了自己的回归测试。两次都挂 `format_test.format_locale`：实际输出 `75bcd15`、`-0b111010...`、`     30071`，缺分隔符。其余 119 个测试通过。
4. 挂因：理解偏差 / 改法不够。DS 认定"分组只对十进制有意义"，于是干脆在非十进制时不做本地化。这能修好题面的症状（进制被忽略），但上游的设计是"进制 + 分隔符都要"，隐藏测试要求非十进制也按 locale 分组。DS 的判断是个看似合理但与上游相反的设计取舍。题面并没有说分组应不应该应用到十六进制。
5. 类别：E（隐藏要求：非十进制也要分组，题面没说）为主；副类 A（题面症状窄，正确修法要更通用，要把进制生成并入分组路径）。
6. 动手前可见信号：弱。题面标题 "Localized formatting is always decimal" 只说"总是十进制"，没说"十六进制要有分隔符"。可见线索是：用 `{:L}` 时 locale 的分隔符与分组本来就是这个特性的核心，"让 L 遵守 type"这句话的自然读法其实是"L 与 type 叠加"，而 DS 选择了"type 优先、L 丢弃"。这是一个可以预判的歧义点（"遵守 type" 是否包含"仍加分隔符"），但仅从题面不能断定，更多是"看不太出，仅有'设计取舍有歧义'这一点"。另外：这是一个 C++ 头文件模板库，需要重写核心函数，改动量比 DS 的 5 行大，但这点也只有看了源码才知道。
7. 把握：高（失败测试输出与 DS 的改法直接对应）；信号判断为中。

## 3. gin-gonic__gin-1957（两次都挂，编译失败）
1. 题目要什么：加 HTTP header 绑定功能，让 `c.ShouldBindHeader(&h)` 可用，把 header 值按 `header:"Rate"` 标签绑进结构体。
2. 标准答案：新增 `binding/header.go`（`headerBinding`、`mapHeader`、`headerSource`，用 `CanonicalMIMEHeaderKey`），`binding.go` 注册 `Header`，`context.go` 加 **`BindHeader`**（MustBindWith，失败时 abort 400）和 **`ShouldBindHeader`** 两个方法，另有 README。
3. DS 两次：两次的 `binding/header.go` 与 binding.go 注册基本与标准答案相同（run1 把 mapHeader/headerSource 放在 form_mapping.go，run2 放 header.go，功能等价）。两次都只加了 `ShouldBindHeader`，没加 `BindHeader`。run1 还自己写了测试 `TestHeaderBinding`、`TestContextShouldBindWithHeader`。两次的失败：`context_test.go:1454:22: c.BindHeader undefined`，整个 `gin` 包测试编译失败，所以 2 个 F2P 加 13 个 P2P（TestContextBindWithJSON 等）全部"挂"。
4. 挂因：漏改一处（API 对称性）。题面示例只出现 `ShouldBindHeader`，但 gin 里每种绑定（JSON/XML/YAML/Query/Uri）都成对提供 `BindXxx`（MustBind）和 `ShouldBindXxx`。DS 没有照既有约定补 `BindHeader`。因为 `context_test.go` 同包编译，缺一个方法就把整个包的所有测试带挂，所以 P2P 全红是连带效应，不是改坏了老行为。
5. 类别：B（需遵守仓库既有 API 约定）为主；副类 E（题面只提到 `ShouldBindHeader`，`BindHeader` 属隐藏要求）、C（要同时在多处补 API）。
6. 动手前可见信号：有，具体：看 `context.go` 里 `BindJSON/BindXML/BindYAML/BindQuery/BindUri` 和 `ShouldBind*` 一一成对，且 `binding.go` 里每个绑定都有对应变量。题面标题 "support bind http header param"（用词 "bind"）本身也不限于 Should 版本。只要照 YAML 或 Uri 的实现完整复制一遍（run1/run2 都在复制 Uri 风格），就会看到成对 API。所以这题对"照既有约定补全对称 API"的检查有信号。run1 最终消息里没有解释为何不加 BindHeader，说明它没有做这个对称性检查。
7. 把握：高。

## 4. google__gson-1100（两次都挂，改动完全相同）
1. 题目要什么：用 `setDateFormat("yyyy-MM-dd")` 序列化 Date 字段为 null 的对象时抛 NPE，要求能正常输出 null。
2. 标准答案：改 `DefaultDateTypeAdapter.java` 两处：`write` 里 value==null 就 `out.nullValue()`；`read` 里 peek 是 NULL 时 `in.nextNull()` 返回 null，并把原来"不是字符串就抛 JsonParseException"改成交给 `nextString()` 抛 IllegalStateException。测试：`testNullValue` 同时检查 `fromJson("null")==null` 与 `toJson(null)=="null"`；`testUnexpectedToken`（非 F2P，未列入）。
3. DS 两次：diff 逐字相同，只改了 `write`（加 null 判断）。两次都挂 `testNullValue`：`JsonParseException: The date should be a string value`，发生在 `read`（测试第 166 行，`fromJson("null")`）。
4. 挂因：漏改一处（读写对称）。题面只有序列化（toJson）的 NPE 栈，DS 只修了报错那一条路径，没有想到同一个适配器的 `read` 在 JSON null 时也会抛错（`read` 先检查 `peek()!=STRING` 就抛）。题面给出的栈里没有 read，但 `read` 与 `write` 紧挨在同一个文件、同一个类。run1/run2 也都提到"运行测试有 5 个因 JDK 日期格式差异失败"，把测试噪声当环境问题，没有去专门写一个 `fromJson("null")` 的验证。
5. 类别：C（同一文件内要同时改 write/read 两处，对称性）为主；副类 A（题面场景窄：只描述 toJson，正确修法要覆盖 null 的往返）。
6. 动手前可见信号：有。仓库里该文件的 `read` 一眼可见：第一行 `if (in.peek() != JsonToken.STRING) throw ...`，对 NULL 同样会抛；而 Gson 的惯例是适配器要么用 `.nullSafe()`、要么自己同时处理 read/write 的 null。题面栈里 `TypeAdapterRuntimeTypeWrapper` / `ReflectiveTypeAdapterFactory` 的路径说明这是普通字段写入，读取同理。因此"修 write 时顺手看 read"是可以预见的检查点。DS 只用 7-8 轮结束，没有再看 read，是明显的过早收敛。
7. 把握：高。

## 总览
- caddy-6345：E（位置歧义，DS 改错地方）；run1 靠先 grep 核实缺口而过。
- fmt-3750：E+A（设计取舍与上游相反：非十进制也要分组）。
- gin-1957：B+E+C（缺 BindHeader，整个包编译失败，P2P 全红是连带）。
- gson-1100：C+A（只修 write，漏 read 对 null）。
- 共同点：4 题 DS 都"自己的验证通过"，但验证只覆盖自己理解的路径；没有一题是环境问题（F）。
