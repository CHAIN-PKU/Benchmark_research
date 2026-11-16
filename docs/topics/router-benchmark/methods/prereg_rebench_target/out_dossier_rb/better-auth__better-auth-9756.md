**Drizzle 适配器 where 子句档案**

我一共做了十余次搜索和阅读。所有行号都来自当前快照。

**【1 题面要点】**
- 要求：`findOne`、`findMany` 的 `where` 里同时有 AND 和 OR 连接符时，两组条件都要生效。
- 期望的 SQL 形式：`WHERE (condition1 AND condition2) AND (condition3 OR condition4)`。
- 复现：邮箱 `contains "company.com"`（隐式 AND）加上姓名 `contains "Admin"`（`connector: "OR"`）。题面称预期返回 2 个用户，实际只返回 1 个。
- 根因：`convertWhereClause` 返回 `[andClause, orClause]`，调用方只用了 `clause[0]`。
- 题面没有给具体修法，只说"两组应被合并"。
- 题面的预期有语义疑点：这个例子里 AND 组只有 1 个条件，OR 组也只有 1 个条件。按题面的 `(AND组) AND (OR组)` 写法，结果是两个条件都要满足，只会得到 1 个用户，不是 2 个。要得到 2 个用户，需要 `A OR B` 的语义。
- 所以"预期 2 条"与"AND 组 AND OR 组"的 SQL 写法互相矛盾，这是最大的歧义。

**【2 相关代码】** 文件均为 `packages/drizzle-adapter/src/drizzle-adapter.ts`：
- `convertWhereClause`，254 行起，负责把 `Where[]` 转成 drizzle 的 `SQL[]`。
  - 只有 1 个条件时走 257–~360 行的单条快捷路径，直接 `return [eq(...)]` 之类。
  - 多条件时，约 375 行先拆出 `andGroup` 和 `orGroup`，再分别构造 `andClause`（379 行）和 `orClause`（482 行）。
  - 约 590–594 行把它们 push 成数组 `clause` 返回。
- `findOne` 在 666 行起，702 行用了 `where: clause[0]`，这是 joins 实验路径，使用关系查询 API。
- `findMany` 在 752 行起，796 行同样用 `where: clause[0]`。
- 非 joins 路径使用 `.where(...clause)`：745、862 行（findMany/findOne 的普通路径）、871、880、889、895、901、933、965 行，另外 `update` 在 148 行。
- drizzle 的 `.where()` 只接受一个参数，所以展开的第二个元素同样被丢弃。bug 不只出在 `clause[0]` 上，所有 `.where(...clause)` 调用点都受影响。

**【3 并列与牵连】**
- 同一个 `convertWhereClause` 的调用点有 10 个以上：`update`、`updateMany`、`delete`、`deleteMany`、`count`、`findOne`、`findMany` 等。最稳妥的修法是让 `convertWhereClause` 返回合并后的单个 `SQL | undefined`，调用点统一改成 `.where(clause)` 和 `where: clause`。
- 只改 `clause[0]` 的两处不够，普通路径会仍然出错。
- 单条件快捷路径返回的是数组，改返回类型时要同步处理。
- `convertWhereClause` 的 AND 组和 OR 组构造代码约 100 行重复。
- 并列实现：
  - `packages/kysely-adapter/src/kysely-adapter.ts`：`convertWhereClause` 返回 `{and, or}`，调用方用链式 `.where(and组)` 再 `.where(or组)`，也就是 `(AND组) AND (OR组)`。
  - `packages/memory-adapter/src/memory-adapter.ts` 约 204 行：从第一条记录开始顺序折叠，OR 用 `||`，其余用 `&&`，是左结合语义，和 kysely 不同。
  - 三个适配器的语义并不一致，这是问题的核心歧义，也是难点。
- 影响面：Drizzle 的 pg、mysql、sqlite 三种 provider，以及 `packages/better-auth/src/adapters/drizzle-adapter/index.ts`，它只是 `export * from "@better-auth/drizzle-adapter"`。
- 受影响的调用方包括使用 OR 的插件、`core/src/db/adapter/factory.ts`、`packages/test-utils/src/adapter/suites/basic.ts`。

**【4 现有测试与约定】**
- `packages/drizzle-adapter/src/drizzle-adapter.test.ts` 是 mock 单元测试，只有"创建适配器"和"MySQL 无 id 创建回退"等用例，没有涉及 where 连接符的断言。我没有找到引用 `connector` 的行。
- e2e 适配器测试在 `e2e/adapter/test/drizzle-adapter/`（pg/mysql/sqlite/plural-joins），依赖真实数据库。
- 共用套件在 `packages/test-utils/src/adapter/suites/basic.ts`，里面有 `connector` 相关用例，三个适配器共用。隐藏测试很可能加在这里，或者加在 drizzle 的 mock 测试里。
- 约定：没有找到文档化的外部规范。参考实现有两个，kysely 是 `(AND组) AND (OR组)`，memory 是顺序折叠，二者在多条件时结果不同。
- 与题面的冲突：题面预期 2 个用户，按 kysely 的语义得到 1 个，按 memory 的顺序折叠得到 2 个。

**【5 边界与隐含要求】**
- 只有 AND 组或只有 OR 组：`and()`、`or()` 对空参数会返回 `undefined`，合并时要过滤掉。
- `where` 为空或 undefined：当前 `findMany` 传 `[]`，改成单值后要返回 `undefined`，让 `.where(undefined)` 等于不加条件。
- 单条件快捷路径（257 行起）要保持一致。
- OR 的单个条件前面带 AND 条件时，位置和顺序是否影响语义。
- `in`、`not_in`、`contains`、`starts_with`、`ends_with`、`lt/lte/gt/gte`、`ne`、null、insensitive 模式在 AND 和 OR 两套重复代码里都要对应。
- 调用点里 `update` 路径（144 行）还对 `updatedWhere` 做了转换，需要确认与新的返回类型兼容。
- 与 joins 路径的 `findFirst({where})` 兼容，该接口接受单个 SQL。
- 题面指出 `findMany`、`findOne`，但 delete、count 同样受影响，应一并修。

**【6 改动规模】**
- 核心只改 1 个文件，即 `drizzle-adapter.ts`。
- 约 12 处：`convertWhereClause` 的返回值（约 590–594 行）、两处 `clause[0]`、约 10 处 `.where(...clause)`。
- 可选：把重复的 AND/OR 构造抽成一个条件构造函数，规模会更小。
- 另加测试 1–2 个。
- 属于局部修补，不需要新增接口，也不是贯穿多层的改动。

**【7 难点一句话】**
改动本身很机械，真正的难点是确定 AND 和 OR 的合并语义：题面的 `(AND组) AND (OR组)` 和它给的"期望 2 条"互相矛盾，而 kysely 与 memory 适配器各自采用不同语义，隐藏测试会偏向哪一种需要猜。