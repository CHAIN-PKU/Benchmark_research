我已经查证完毕，下面直接给档案。

## 档案

**【1 题面要点】**
- 要求：`command getkeys eval "return 1" 0` 应返回空数组，而不是报错。
- 实际行为：`(error) ERR Invalid arguments specified for command`。
- 题面没给修法，只给了复现命令和期望输出。关键句：
  - "Returns an empty array."
  - "at least a separate error should be returned"
  - "Is there a reason we should return an error here instead of an empty array of keys?"
- 作者不确定这是不是有意为之。

**【2 相关代码】**
- `src/server.c:5890` 的 `getKeysSubcommand`：
  - `src/server.c:5908` 是 `if (!getKeysFromCommand(...)) addReplyError("Invalid arguments specified for command")`。
  - 它把 "返回 0 个 key" 一律当作错误。
- `src/db.c:1679` 的 `genericGetKeys`：
  - `src/db.c:1683` 用 `atoi` 解析 numkeys。
  - `src/db.c:1686` 的 `if (num < 1 || num > (argc - firstKeyOfs)/keyStep)` 在 `num==0`、负数、超长时都返回 0。
  - 代码注释写的是 "Don't return any key if the command is going to reply with syntax error"。
- `src/db.c:1717` 的 `evalGetKeys` 调用 `genericGetKeys(0,2,3,1,...)`。
- `src/server.c:1753-1779` 里 eval、eval_ro、evalsha、evalsha_ro 都用 `evalGetKeys`，key spec 是 `KSPEC_FK_KEYNUM`。

**【3 并列与牵连】**
- 并列调用方：`genericGetKeys` 被 sintercard、zunion/zinter/zdiff、zunionstore 等 store 变体、lmpop、blmpop、zmpop、bzmpop 共用。
  - 其中 sintercard、zunion 系、lmpop、zmpop 系的 numkeys 为 0 才是真正的语法错误，不能一并改成返回空数组。
  - eval 系 numkeys=0 是合法的。
  - 因此很可能只能让 eval 系特殊处理，或者把 "语法错误" 与 "合法但无 key" 区分开。
- 其他 `getKeysFromCommand` 调用点：
  - `src/tracking.c:226`
  - `src/acl.c:1315`
  - `src/cluster.c:5949`
  - `src/module.c:10085`（`RM_GetCommandKeys`）
  - 这些调用点只看 numkeys，返回 0 都按 "无 key" 处理，行为不变。
- `RM_GetCommandKeys` 在 `src/module.c:10088` 对 0 个 key 返回 NULL 且 `errno=0`，与 EINVAL 区分，已经隐含 "0 个 key 合法" 的语义。
- 其他 getkeys 函数也都用 "返回 0" 表示语法错误：
  - `xreadGetKeys` 在 `src/db.c:1911`
  - `lcsGetKeys` 在 `src/db.c:1876`
  - `getKeysUsingLegacyRangeSpec` 在 `src/db.c:1599`
  - `moduleGetCommandKeysViaAPI`

**【4 现有测试与约定】**
- `tests/unit/introspection-2.tcl:80-90` 只有 GET、MEMORY USAGE、XGROUP 三条正向用例。
- `tests/unit/sort.tcl:98-103` 断言 `{abc def}`。
- `tests/unit/moduleapi/getkeys.tcl:28-30` 断言 `eval "" 4 key1..key4` 返回四个 key。
- `tests/unit/moduleapi/getkeys.tcl:40-43` 断言 arity 错误返回 `*EINVAL*`。
- 仓库里没有任何用例覆盖 "getkeys 返回错误 Invalid arguments"。grep 该报错串，只在 `src/server.c:5909` 出现。
- 没有找到 eval numkeys=0 的现有测试，因此与题面期望没有冲突。
- 隐藏测试很可能是 `r command getkeys eval "return 1" 0` 期望 `{}`。可能还会有负数、numkeys 大于参数个数的错误用例，以及 `RM_GetCommandKeys` 用例。

**【5 边界与隐含要求】**
- `numkeys` 为负数、非数字（`atoi` 得 0）或大于实际参数个数时，仍应报错，不能被 "0 合法" 吞掉。
- `atoi` 把非数字解析成 0，会与合法的 0 混淆，需要用严格解析（如 `string2l`）来区分。
- `evalsha` 和 `eval_ro` 也要同样生效。
- 返回空数组时要避免对 `result.keys` 做错误访问。`getKeysPrepareResult` 的 count 为 0 时要小心。
- 不能破坏 sintercard、zunion 等 numkeys=0 仍应报错的行为。
- `RM_GetCommandKeys` 的 errno 语义需保持一致。

**【6 改动规模】**
- 最小方案：改 `src/db.c` 里 `genericGetKeys` 或 `evalGetKeys`，再改 `src/server.c:5908` 的判断，共 2 个文件、约 3-4 处，属于局部修补。
- 干净方案：让 getkeys 函数用返回值区分 "错误" 与 "0 个 key"，需要改动所有 getkeys 实现的返回约定和调用方。
  - 这是贯穿多层的重构，涉及约 5 个文件。
  - 它是一个可选路线，未必是必须的。
- 另需新增测试，在 `tests/unit/introspection-2.tcl` 加几条用例。

**【7 难点一句话】**
"返回 0 个 key" 同时代表语法错误和合法的空结果，而 `genericGetKeys` 被多条命令共用且语义不同，难点在于只放开 eval 系而不误伤 zunion 等仍应报错的命令，同时严格区分数字 0 和非法值。