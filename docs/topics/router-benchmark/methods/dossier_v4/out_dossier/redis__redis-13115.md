# 仓库档案：Lua 数字转参数时 n×10^8 触发 HINCRBY 报错

## 【1 题面要点】
- 要求的行为：在 Lua 脚本里执行 `redis.call("HINCRBY","key","field",tonumber(ARGV[1]))`，当值形如 n×100,000,000（1e9、1.1e9、1.2e9……）时，应像 6.2/7.0 那样成功，不能报 `ERR value is not an integer or out of range`。
- 题面给出了复现脚本（node 客户端，循环 0 到 2e9，步长 1e7）。它还对比了 7.2 的实际输出：1.0e9、1.1e9、1.2e9 等失败，1.05e9、1.15e9 等成功。
- 期望输出已给出，即 6.2 下全部成功。
- 题面没有给修法建议，也没有定位到源码。
- 开头一句「if and only if n * 100,000,000」说得不准，实际规律见【5】。

## 【2 相关代码】
- `src/script_lua.c:818-824`，`luaArgsToRedisArgv`（约 790-857 行）：
  - 参数是 LUA_TNUMBER 时，用 `fpconv_dtoa((double)num, dbuf)` 转成字符串。
  - 注释写「不能用 lua_tolstring，因为精度丢失」。
  - 这里就是 bug 的触发点：1e9 被写成 `"1e+09"`，HINCRBY 解析失败。
- `deps/fpconv/fpconv_dtoa.c:249-319`，`emit_digits`：
  - 253 行 `if (K >= 0 && (exp < (ndigits + 7)))` 才输出「纯整数」。
  - 1e9 的 digits="1"、K=9、ndigits=1、exp=9。条件 9<8 不成立，落入科学计数法，得到 `1e+09`。
  - 1.05e9 的 ndigits=3、K=7、exp=9。条件 9<10 成立，输出 `1050000000`。这解释了为什么只有部分值失败。
  - 284 行 `ndigits = minv(ndigits, 18 - neg)` 属于科学计数法分支。
- `fpconv_dtoa`（349-373 行）是入口，`grisu2`（226-247 行）负责生成最短数字。
- `src/util.c:661-692`，`d2string`：
  - 先用 `double2ll` 判断能否安全转成 long long，能就走 `ll2string` 输出纯整数；否则才走 `fpconv_dtoa`。
  - 这是现成的整数优先路径。

## 【3 并列与牵连】
`fpconv_dtoa` 的调用点：
- `src/script_lua.c:822`，没有整数分支，是出问题的地方。
- `src/util.c:686`（`d2string` 内部，已有整数分支）。
- `src/rio.c:517`（`rioWriteBulkDouble`，没有整数分支，用于 AOF/重写）。
- `src/rdb.c:602`（zset 分值的 RDB 文本形式）。
- `src/debug.c:198、212`。

`d2string` 的调用点：
- `networking.c:880、891`。
- `t_zset.c:1099`。
- `module.c:2681`。

牵连影响：
- 若改 `emit_digits`，会影响 rio、rdb、debug 的输出格式，也就是持久化格式，风险较大。
- 若只改 `script_lua.c`，范围最小。可以改用 `d2string`，或在 `lua_tonumber` 之后先尝试 `double2ll`。
- Lua → Redis 的返回值路径是 `script_lua.c:623`（`addReplyLongLong`）和 `:669`，是另一方向，与本题无关。
- 6.2 的参数转换走 `lua_tolstring`，即 `%.14g`（`deps/lua/src/luaconf.h:523`）。1e9 会输出 `1000000000`。

## 【4 现有测试与约定】
- `tests/unit/scripting.tcl:836-842`，「Number conversion precision test (issue #1118)」：`local value = 9007199254740991; redis.call("set","foo",value); get foo` 断言 `{9007199254740991}`。
  - 这个值走 fpconv 的纯整数分支（ndigits=16、exp=15<23），所以现在能通过。
  - 修复后必须仍然通过。
- `tests/unit/scripting.tcl:844-849` 断言 `12039611435714932082`，这是字符串，不经过数字转换。
- 没有找到任何对 `fpconv_dtoa` 的 C 单测。
- `tests/unit/type/zset.tcl:2615` 断言 `1.7976931348623157e+308`，说明科学计数法输出对浮点分值是被测试约定的，不能随意改。
- 约定：`d2string` 对「能无损转为 long long 的值」输出整数，这是仓库里已有的参考做法。
- 与题面期望不冲突。
- 隐藏测试大概率是在 `scripting.tcl` 里加一条，用 `redis.call('hincrby'/'set'/'incrby', ..., 1e9 或 tonumber(...))` 之类的脚本，断言结果是整数。

## 【5 边界与隐含要求】
- 失败的值并非只有 n×1e8，而是所有「有效数字很少、末尾 0 很多」的整数。
  - 例如 1e10、3e9、1.5e10，以及 1e15 一类。
  - 条件是 exp ≥ ndigits+7，也就是尾部 0 的个数 ≥ 7。
- 负数：1e9 取负时前面带 `-`，要保证也输出 `-1000000000`。
- 大整数：超出 long long 范围的 double（如 1e19）无法走整数路径，会走科学计数法。6.2 此时输出 `1e+19`，所以行为一致，不需要特别处理。
- 小数：0.5、1e-9 等仍应保持当前输出，不要回退成 `%.14g`，否则会重新引入 issue #1118 的精度丢失。
- 零和 -0：`d2string` 已处理，直接用 `fpconv_dtoa` 的零值会输出 `0`。
- NaN 和 inf：原样保留。
- 缓冲区：`dbuf[64]` 足够。`d2string` 用 `ll2string` 写入时要传对长度。
- 结果需要在缓存对象复用路径（830-837 行）里保持 `obj_len` 与内容一致。

## 【6 改动规模】
- 最小修法：1 个文件（`src/script_lua.c`）改 1 处，约 3-5 行，再加 1 条回归测试（`tests/unit/scripting.tcl`）。
- 若选择修 `emit_digits`（deps/fpconv），则是 1 个文件改 1 个条件，但会牵连 rio、rdb 等持久化输出，需要更谨慎地评估。
- 都是局部修补，不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
定位本身不难，从报错顺着 `luaArgsToRedisArgv` 到 `fpconv_dtoa` 的 `emit_digits` 条件就能找到。难点在于选对修复层：只改 Lua 参数转换、还是改 fpconv 库，并且要保证仍不丢精度、不改变其他调用点（持久化、zset 输出）的格式。