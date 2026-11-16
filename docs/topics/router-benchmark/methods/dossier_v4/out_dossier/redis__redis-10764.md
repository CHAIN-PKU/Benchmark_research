**档案：BZMPOP 把非 key 参数也当作阻塞 key**

我读了 `t_zset.c`、`t_list.c`、`db.c`、`blocked.c`，并统计了测试里的出现次数。没有逐条读 `tests/unit/type/zset.tcl` 里的 BZMPOP 用例，所以第 4 节的断言行号没有引用。

**【1 题面要点】**
- 要求的行为：`BZMPOP timeout numkeys key... MIN|MAX [COUNT n]` 只应在 numkeys 声明的那几个 key 上阻塞。现在它还会在 timeout、numkeys、MIN/MAX、COUNT 和 count 值这些非 key 参数上阻塞。
- 复现（题面给出）：
  - 客户端 1 执行 `bzmpop 100 1 myzset max count 10`，用户 ACL 是 `~my*`。
  - 客户端 2 执行 `zadd max 1 one 1 two 3 three`。
  - 客户端 1 被唤醒，返回 `max` 这个 key 的数据，绕过了 ACL。
- 期望（题面原话）："Client 1 should have been blocked waiting for myzset to be written."
- 修法建议（题面原话）：用 `getKeysFromCommandWithSpecs` 之类取 key 的方式来决定阻塞哪些 key。这只是作者的个人看法，不是硬性要求。
- 题面没有给期望输出的完整文本，也没有指定测试写法。

**【2 相关代码】**
- `src/t_zset.c:4044`：`blockingGenericZpopCommand` 末尾调用 `blockForKeys(c,BLOCKED_ZSET,c->argv+1,c->argc-2,...)`。
  - 这是根因。`argv+1` 和 `argc-2` 只适合 BZPOPMIN/BZPOPMAX（`key... timeout`）。
  - 对 BZMPOP，`argv[1]` 是 timeout，之后依次是 numkeys、key、MIN/MAX、COUNT，于是这些都被登记成阻塞 key。
  - 函数已经收到正确的 `keys` 和 `numkeys` 参数，前面的查找循环用的就是它们（`t_zset.c:4003-4005`），只有最后一步用了错的。
- `src/t_zset.c:4309-4360`：`zmpopGenericCommand` 解析 numkeys、where 和 COUNT。阻塞时传入 `c->argv+numkeys_idx+1` 和 numkeys（`:4355`），key 是正确的。
- `src/t_zset.c:4048-4055`：`bzpopmin` 和 `bzpopmax` 传入 `argv+1` 和 `argc-2`，所以它们不受影响。
- `src/blocked.c:729`：`blockForKeys` 对每个 key 登记 `c->bpop.keys` 和 `db->blocking_keys`。
- `src/blocked.c:338-394`：`serveClientsBlockedOnSortedSetKey` 唤醒时用 `rl->key`，并靠 `lastcmd->proc == bzmpopCommand`（`:361`）判断用嵌套数组回复。

**【3 并列与牵连】**
- 并列实现是 `t_list.c:1031` 的 `blockingPopGenericCommand`（BLMPOP）。它在 `:1094` 传的是 `keys,numkeys`，是正确的，不用改。
- 参照对象：BLMPOP 的写法正是 zset 这边应该照做的。
- `blockForKeys` 的其他调用点（`t_list.c:1119` BLMOVE、`t_stream.c:2406`、`module.c:7099`）都是传显式 key，不受影响。
- 修改只影响 BZMPOP 的阻塞登记。BZPOPMIN 和 BZPOPMAX 传入的 `keys` 就是 `argv+1`，行为不变。
- ACL 和 key-spec 这边不用动。`db.c:2158` 的 `bzmpopGetKeys` 用 `genericGetKeys(0,2,3,1,...)`，已经正确，只是阻塞路径没用它。

**【4 现有测试与约定】**
- `tests/unit/type/zset.tcl` 里有约 56 处 BZMPOP 相关出现，`tests/integration/aof.tcl` 有 9 处。我没有逐条读，不引用具体断言行号。
- 这些测试大多是普通阻塞、超时和嵌套回复格式。没有看到针对"非 key 参数导致误唤醒"的测试，所以隐藏测试很可能是新增这类用例。
- 约定：BLMPOP 的实现就是参考。与题面期望没有冲突。

**【5 边界与隐含要求】**
- 登记的 key 必须和 `numkeys` 一致。多个 key 时保持顺序，重复 key 由 `blockForKeys` 里 `dictAdd` 失败后跳过的逻辑处理。
- 测试多半要覆盖这几种情况：
  - 用名为 `max`、`min`、`count`、timeout 数值（如 `100`）、numkeys（如 `1`）的 key 去写，客户端必须仍然阻塞。
  - 写真正的 key 时能被正常唤醒，复制到副本和 AOF 的命令正确。
- BZPOPMIN/BZPOPMAX 的回归行为不能变。
- 被误登记的 key 也会影响 `blocking_keys` 的清理，这一点修复后自然消失。

**【6 改动规模】**
- 1 个文件、1 处：`t_zset.c:4044` 把 `c->argv+1,c->argc-2` 换成 `keys,numkeys`。
- 局部修补，不需要新结构，也不需要贯穿多层。
- 测试需要在 `tests/unit/type/zset.tcl` 另加用例。

**【7 难点一句话】**
改动本身很小，难点是定位：要认出 `blockForKeys` 用的是硬编码的 `argv+1/argc-2`，而不是函数已经拿到的 `keys/numkeys`。