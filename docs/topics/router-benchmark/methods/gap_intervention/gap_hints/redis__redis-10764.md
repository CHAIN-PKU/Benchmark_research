## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
1. `src/t_zset.c` 的 `blockingGenericZpopCommand`：函数前半段遍历的是参数 `keys/numkeys`，末尾调用 `blockForKeys` 时却用了 `c->argv+1, c->argc-2`。这个写法只对 BZPOPMIN/BZPOPMAX 成立，对 BZMPOP 不成立。
2. `src/t_list.c` 的 `blockingPopGenericCommand`（BLMPOP 和 BLPOP 共用）：它向 `blockForKeys` 传的是 `keys,numkeys`。这是并列实现，可以拿来对照；也请核对它有没有同类问题。
3. `src/blocked.c` 约第 361 行、`lastcmd->proc == bzmpopCommand` 一带：解除阻塞后重新执行命令时，会用到命令参数和 key 的对应关系。请确认阻塞的 key 集合改动后，这里仍然一致。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
1. 参数值恰好与 `timeout`、`numkeys`、`MIN`、`MAX`、`COUNT` 或 count 数值同名的 key，在 key 不存在时被写入。
2. 多个 key 的 BZMPOP，其中部分 key 不存在，并且 key 名与非 key 参数同名。
3. 对照检查 BZPOPMIN/BZPOPMAX 的行为是否保持不变。它们的 timeout 是最后一个参数，同样不能被当成 key。

**C. 仓库里已有的约定、文档或测试中，与这个行为有关的地方**
1. `src/db.c` 的 `bzmpopGetKeys` 和命令的 key specs，是已有的 key 位置约定（题面提到可参考 ACL 取 key 的方式）。对阻塞的 key 范围要与它保持一致。
2. `tests/unit/type/zset.tcl` 和 `tests/unit/type/list.tcl` 里已有的 BZMPOP/BLMPOP 阻塞测试：核对它们的写法和风格，再决定怎么补测试。

**D. 建议提交前额外自测的情况**
1. 复现题面场景：用户只对 `my*` 有权限，执行 `BZMPOP 100 1 myzset MAX COUNT 10` 后，另一个客户端 `ZADD max ...`，这时第一个客户端不应被唤醒。
2. 随后向 `myzset` 写入数据，确认客户端被正常唤醒，且返回内容和复制出去的命令都正确。
3. 用 `CLIENT LIST` 或 `INFO` 里的 blocked_keys 数量，核对阻塞的 key 数量等于 numkeys。再回归一遍 BZPOPMIN/BZPOPMAX 和 BLMPOP。
