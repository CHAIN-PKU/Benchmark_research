**档案：ACL LIST 中子命令规则残留（`-config|set` 未被后来的 `+config` 清掉）**

说明：下面的行号和代码都是我在这份快照里实际读到的。第 2 节里"根因"那段是我读代码推出来的，没有运行复现。

**【1 题面要点】**
- 要求的行为：`ACL SETUSER user1 on >123 +config|get -config|set`，再执行 `ACL SETUSER user1 +config` 之后，`ACL LIST` 不应再显示 `-config|set`。
- 题面给了复现步骤：这两条 SETUSER、`ACL LIST`，以及用 user1 登录后执行 `CONFIG SET`。
- 实际输出：`... resetchannels -@all -config|set +config`。
- 期望输出（照抄）：`"... resetchannels -@all +config"`，并说 "the **-config|set** should not show"。
- 题面没有给修法建议。题面写的是"显示与实际权限不符"，但从代码看，实际权限（`CONFIG SET` 返回 OK）本身是对的，错的是保留下来的规则字符串。

**【2 相关代码】**（均在 `src/acl.c`）
- `ACLSelectorRemoveCommandRule`（550–590）：新增规则前，从 `selector->command_rules` 里删掉旧规则。精确匹配要删。新规则是父命令（如 `config`）时，也要删掉 `config|xxx` 子命令规则（578–579）。
- 根因（我的推断）：删除后用 `memmove(copy_position, copy_end, ...)` 把后面的规则前移（582），但紧接着执行 `existing_rule = copy_end`（585）。`copy_end` 仍指向移动之前的位置，所以下一条规则已经移到 `copy_position`，循环会跳过它。
- 按题面的例子推演：规则串是 `-@all +config|get -config|set`。`+config|get` 被删，后面的 `-config|set` 前移，却被跳过，所以残留。
- `ACLUpdateCommandRules`（594–602）：先调用 Remove，再在末尾追加 `+/-rule`。
- `ACLSetSelector`（1008 起）：
  - `+cmd` 在 1095–1158，其中 1103 和 1156 调用 UpdateCommandRules。
  - `-cmd` 在 1159–1166，其中 1166 调用 UpdateCommandRules。
  - 类别规则走 `ACLSetSelectorCategory`（680–689，684 调用 UpdateCommandRules）。
- `ACLChangeSelectorPerm`（606–619）：设置 command bit，对容器命令也会设置所有子命令的 bit，所以实际权限是对的。
- 输出端：754–762 附近生成 `ACL LIST` 和 `GETUSER` 的 commands 字符串。
- 重载：`ACLRecomputeCommandBitsFromCommandRulesAllUsers`（645–678）按 command_rules 重放规则。残留的 `-config|set` 会被重放，这里最后也靠 `+config` 的位置在后，所以结果不变。

**【3 并列与牵连】**
- 并列实现：修的是同一个 Remove 函数，`+`、`-`、`@category` 三条路径都共用它。不需要另外并列改动。
- 影响面：`ACL LIST`、`ACL GETUSER` 的 commands 字段、`ACL SAVE`/aclfile 的持久化、`ACL DRYRUN`、以及模块加载后重算 bit（645 起）。
- 规则字符串变短后，重放顺序必须保持等价。因为 bit 已经由子命令继承设好，删掉被覆盖的子规则不改变权限语义。

**【4 现有测试与约定】**
- `tests/unit/acl.tcl:389–396`：`ACL setuser newuser -@all +acl +config -config|set`，断言 `assert_match {*-config|set*} $cmdstr`，并且 `CONFIG SET` 返回 NOPERM。这里 `-config|set` 在 `+config` 之后，应该保留，不冲突。
- `tests/unit/acl.tcl:604–613` 是现有的"规则去重和排序"测试：
  - 604–605：`-@all +hget -hset +hset -hget` → `-@all +hset -hget`
  - 608–609：`-@all +client|list +client|list +config|get +config +acl|list -acl` → `-@all +client|list +config -acl`。这条已经覆盖"+config 覆盖 config|get"，但紧挨着只有一个被覆盖的子规则，所以测不出跳过 bug。
  - 612–613：`+select|0 +select|0 +debug|segfault +debug` → `+select|0 +debug`
- 隐藏测试大概率就加在这一段，新增一条类似 `+config|get -config|set +config` 的断言。
- 与题面期望不冲突，是同一约定：以"后来者覆盖先前"为准，规则串保持最简。

**【5 边界与隐含要求】**
- 连续多条规则都要删：`+config|get -config|set +config|x ... +config`，要求每条都被检查。
- 被删的规则是最后一条时，要处理前面的空格（571 已有处理，需保持正确）。
- 被删规则在开头时不能留前导空格。
- 前缀误匹配：`+config` 不应删掉名字以 `config` 开头的其他命令，如 `configx`，所以要依赖 `|` 判断（579 已有）。
- 删除后要保证 `sdsupdatelen` 仍正确（589）。
- `-config` 去覆盖 `+config|get` 同理。
- 多个 selector（`(...)` 形式）每个独立维护 command_rules，不能互相影响。

**【6 改动规模】**
- 1 个文件、1 个函数、约 1–3 行：删除后让指针从 `copy_position` 继续，而不是 `copy_end`。
- 局部修补，不需要新增结构。
- 再加一条测试到 `tests/unit/acl.tcl`。

**【7 难点一句话】**
难点在定位：权限本身是对的，症状出在规则字符串，要想到问题出在"原地删除后指针没回退"这个遍历 bug，而不是权限计算。修的代码很少，改法也很明确。