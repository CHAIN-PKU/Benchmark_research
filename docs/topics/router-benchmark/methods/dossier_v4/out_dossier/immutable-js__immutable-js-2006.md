**档案：filter 之后 slice(负 begin) 被忽略**

说明：我没有运行复现，下面的根因是读代码推断的。`Math.max(0, NaN) | 0` 得 0 这一点是按 JS 语义推出来的。

**【1 题面要点】**
- 要求：`Range(0,10).filter(()=>true).slice(-2).toArray()` 应返回 `[8, 9]`，实际返回 `[0..9]`，即 slice 被忽略。
- 题面给了复现代码和期望输出，没有给修法建议。
- 题面只说"负 begin + filter"。没有 filter 时正常，正 begin 时也正常。

**【2 相关代码】**
- `src/Operations.js:404-` 的 `sliceFactory` 是最可能要改的地方。
  - 407 行：`wholeSlice` 为真就原样返回 collection。
  - 411-412 行：用 `resolveBegin`/`resolveEnd` 解析下标。
  - 414-419 行：注释说"size 未知时负数会解析成 NaN，此时先 cacheResult 再递归"，检测方式是 `resolvedBegin !== resolvedBegin`。
  - 425-466 行：用 `resolvedBegin` 跳过元素，用 `sliceSize` 截断。
- `src/TrieUtils.js:74-86` 的 `resolveIndex` 是根因所在。
  - 负数分支是 `size === Infinity ? size : Math.max(0, size + index) | 0`。
  - filter 之后 `size` 是 `undefined`，`size + index` 为 NaN，`Math.max(0, NaN)` 为 NaN，`NaN | 0` 为 0。
  - 所以结果是 0，不是 NaN，414-417 行的 NaN 检测永远不触发，begin 被当成 0。
  - 这样 `slice(-2)` 变成了 `slice(0)`，也就是"被忽略"。
- `src/TrieUtils.js:58-64` 的 `wholeSlice` 在 `size === undefined` 时对负 begin 返回 false，这部分行为正确。
- `src/TrieUtils.js:88` 的 `isNeg` 负责判断负数（含 -0）。
- `src/CollectionImpl.js:264-266`：通用的 `slice` 调用 `sliceFactory(this, begin, end, true)`。

**【3 并列与牵连】**
- `resolveBegin`/`resolveEnd` 的其他调用点：
  - `List.js:190-191`
  - `Range.js:74-75`
  - `Repeat.js:50`
  - `Stack.js:121-122`
  - `CollectionImpl.js:590`（splice，传入 `index<0 ? this.count() : this.size`，已避开 undefined）
- 这些调用点的 size 基本都是已知的，所以不会碰到 undefined。
- 改 `resolveIndex` 会影响所有调用点。改 `sliceFactory` 只影响 Seq 和惰性集合。
- `take`/`skip`/`butLast`/`takeLast` 等经 `slice` 间接走同一条路径（`CollectionImpl.js:439-467`）：
  - `takeLast(n)` 是 `slice(-n)`，同样会被这个 bug 影响。
  - `butLast` 是 `slice(0, -1)`，`end` 为负，也会受影响。
  - `skipLast` 是 `slice(0, -n)`，同上。
- `resolveEnd` 对负 end 同样会得到 0，不是 NaN。`filter(...).slice(0,-1)` 很可能同样出错，这是并列问题。

**【4 现有测试与约定】**
- `__tests__/slice.ts:10-11`：`Seq([1..6]).slice(-3,-1)` 得 `[4,5]`，`slice(-1)` 得 `[6]`。这些是已知大小的情况。
- `__tests__/slice.ts:117`：`Seq({a,b,c}).slice(-1).toObject()` 得 `{c:3}`。
- `__tests__/slice.ts:163-168`：`slice(-4,4)` 和 `slice(-3)` 在整体切片时返回原对象（`toBe(s)`、`toBe(v)`）。
- `__tests__/Seq.ts:110-113`：`slice(0, NaN)` 得 `[]`，`slice(NaN)` 得全部。
- `__tests__/List.ts:908-936`：NaN 和 ±Infinity 被当作 0 处理。
- 已有测试里没有"size 未知（filter 之后）+ 负下标"的用例，估计隐藏测试会加在 `slice.ts`。
- 约定是 `Array.prototype.slice` 的语义，与题面期望一致，不冲突。
- 源码注释（Operations.js:414-416）已经写明了设计意图："size 未知则先 cache"。实现没达到注释的意图。

**【5 边界与隐含要求】**
- 负 end 和 size 未知（`filter().slice(0,-1)`、`slice(-3,-1)`）。
- 负 begin 和 size 已知但很小：`wholeSlice` 路径要继续返回原对象。
- `size === Infinity` 时负数保持 Infinity，这是现有行为，不要破坏。
- 无限序列加负下标：cacheResult 会死循环，要看现有逻辑是否有保护（`Infinity` 分支）。
- 正 begin 与未知 size：`resolveIndex` 的 `size === undefined → index` 分支保持不变。
- `-0` 和 NaN 的现有语义要保留。
- `useKeys` 为 true（Keyed/Set）和 false（Indexed）两种路径都要正确。
- `toArray` 之外，`toList`、迭代器路径（`__iteratorUncached`）和 `reverse` 路径也要对。

**【6 改动规模】**
- 局部修补：1 到 2 个文件，几行代码。
- 方案一：改 `resolveIndex`，让 `size` 未定义的负数返回 NaN。
- 方案二：在 `sliceFactory` 里显式检测 `originalSize === undefined` 且 begin 或 end 为负。
- 另外要加测试。
- 不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
难点在定位：NaN 被 `| 0` 悄悄抹成 0，让现有的"size 未知就 cacheResult"保护失效；定位之后改法本身很小，但要避免影响其他调用点和 NaN、Infinity 的既有行为。