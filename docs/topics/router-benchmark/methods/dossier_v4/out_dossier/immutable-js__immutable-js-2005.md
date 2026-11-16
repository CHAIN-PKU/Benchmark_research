我已读完 `OrderedSet`、`Set`、`OrderedMap`、`deepEqual` 和哈希相关代码，也看了现有测试。node_modules 没装，所以我没法跑复现。下面直接给出档案。

**【1 题面要点】**
- 标题是 "OrderedSet equality and hashCode bug"。
- 现象：内容相同的 `OrderedSet`，`equals` 返回 false，`hashCode()` 也不同，结果取决于集合是怎么构造出来的。`Set` 在同样场景下表现正常。
- 复现只有 jsfiddle 链接和两张截图，正文里没有可复制的代码，也没有期望输出和修法建议。
- 从截图推测是同一批元素经不同构造路径（add、remove、再 add 等）得到的集合比较结果不一致，具体路径我无法确认。

**【2 相关代码】**
- `src/OrderedSet.js`：`OrderedSet` 继承 `Set`，只覆盖了构造、`toString`、`__empty` 和 `__make`（makeOrderedSet，约 :55）。它没有自己的 `__hash` 处理，`makeOrderedSet` 里没有 `set.__hash`。
- `src/Set.js`：`updateSet`（约 :213）在有 `__ownerID` 时原地改 `size` 和 `_map`，没有清 `__hash`。`makeSet`（:224）和 `__ensureOwner`（约 :172）也不处理 `__hash`。`__iterate` 和 `__iterator` 委托给 `_map`。
- `src/OrderedMap.js`：`updateOrderedMap`（约 :113）在可变路径里设置 `omap.__hash = undefined`。`__ensureOwner` 传递 `this.__hash`。删除会在 `_list` 里留下 `undefined` 空洞，`__iterate` 用 `entry &&` 跳过，`__iterator` 走 `_list.fromEntrySeq()`。
- `src/CollectionImpl.js:481`：`hashCode()` 缓存到 `this.__hash`。`hashCollection`（:746）对有序集合用 `31*h+hash(v)`，对无序集合用加法。
- `src/utils/deepEqual.js:9`：先比较大小和缓存的 `__hash`，不同就返回 false。有序集合再按 entries 逐项比较，key 取 `entry[0]`。

**【3 并列与牵连】**
- `Map` 和 `OrderedMap` 的 `__hash` 管理比 `Set` 完整：Map.js:92、147、611、651，OrderedMap.js:91、106、159。
- `Set` 和 `OrderedSet` 完全没有对应处理，这是最大的不对称。
- `List.js`（:107、237、406、456、668）和 `Stack.js`（:64、92、110、135、156、219）也做了同样的清缓存。
- 若修在 `Set.js` 的 `updateSet`、`makeSet`、`__ensureOwner`，会同时影响 `Set` 和 `OrderedSet`。
- `OrderedSet` 的 `Set` 迭代路径有个值得注意的点：`isOrdered` 为 true 时 `deepEqual` 的 key 比较，对集合来说 `entry[0]` 是元素本身。
- 改 `hashCollection` 或 `deepEqual` 会影响所有集合类型。

**【4 现有测试与约定】**
- `__tests__/OrderedSet.ts:35-36`：`expect(s1.equals(s2)).toBe(false)`（`of('A','Z')` 对 `of('Z','A')`）。`expect(s1.equals(s2.reverse())).toBe(true)`。这说明 `OrderedSet` 有意区分顺序，修复后这两条必须仍然成立。
- `__tests__/OrderedSet.ts:20`：`OrderedSet().add('A').add('Z').remove('A').add('A')` 的 `toArray` 是 `['Z','A']`。
- `__tests__/Equality.ts:146`：`expect(a.hashCode()).toBe(b.hashCode())`，`:152` 是 `Seq` 不同值哈希不同。
- 目前没看到测试覆盖"可变变更后缓存哈希是否失效"或"OrderedSet 经不同构造路径的 equals 和 hashCode"。
- 文档约定在 `src/is.js:41-55`：equals 为 true 则 hashCode 必须相同。
- 与题面不冲突，但"同元素不同顺序是否应相等"需要按现有测试保持为不相等。

**【5 边界与隐含要求】**
- 我没能确认根因：可能是 `__hash` 在 `Set` 的 `withMutations` 或原地变更后没清；也可能是 `OrderedMap` 空洞或迭代顺序问题。需要在能运行的环境里复现后再定。
- `withMutations` 之后 `asImmutable` 保留的 `__hash` 需要正确。
- 空集合是共享单例，别污染它的 `__hash`。
- 要同时验证 `Set` 和 `OrderedSet`，也要验证顺序敏感性没被破坏。
- 隐藏测试大概率会断言：构造路径不同但元素和顺序相同的 `OrderedSet`，其 `equals` 为 true 且 `hashCode` 相同。

**【6 改动规模】**
- 大概 1 到 3 个文件（`Set.js`、`OrderedSet.js`，可能还有 `OrderedMap.js` 或 `deepEqual.js`），每处几行。
- 属于局部修补，不需要新结构，也不贯穿多层。
- 测试要补在 `__tests__/OrderedSet.ts`。

**【7 难点一句话】**
题面没有文字复现，根因要自己定位：是 `Set` 一族缓存的 `__hash` 失效问题，还是 `OrderedMap` 的迭代顺序问题。判断错了，修复就改在错的层上。