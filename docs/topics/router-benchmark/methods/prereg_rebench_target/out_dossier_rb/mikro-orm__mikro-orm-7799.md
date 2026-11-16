# 仓库档案：`orm.migrator.up()` 改写快照

说明：我没有看到复现仓库，因为是离线快照。下面关于"哪些字段会漂移"的判断来自读代码，不是跑出来的。

## 【1 题面要点】
- 要求的行为：`migrator.up()` 之后，快照里"一堆内容是错的，要手动 revert"。隐含期望是 `up()` 后快照与 `create()` 写出的快照一致，或至少不被改坏。
- 复现：只给了外部仓库链接 `zachkirsch/mikro-orm-migrate-snapshot-repro`，没有内联代码和期望输出。
- 修法建议：没有。
- 驱动是 `@mikro-orm/sqlite`，版本 7.1.2-dev.10。
- 题面没说"错"具体指哪些字段，要靠读代码推断。

## 【2 相关代码】
- `packages/migrations/src/Migrator.ts:197-225`，`runMigrations()`：
  - `up`/`down` 执行完后，用 `DatabaseSchema.create(connection, platform, config, …, ctx)`（`:205-215`）对真实数据库做内省，再调用 `storeCurrentSchema(schema)`。
  - 内省失败时由 `catch {}` 静默吞掉（`:217-221`）。
- `Migrator.ts:339-348`，`storeCurrentSchema(schema?)`：
  - 默认值是 `this.#schemaGenerator.getTargetSchema()`，也就是来自元数据的版本。
  - 写入方式是 `JSON.stringify(schema, null, 2)`。
- `Migrator.ts:114` 和 `:184`，`create()` 和 `createInitial()`：它们写快照时走元数据路径。
- `Migrator.ts:280-337`，`getSchemaFromSnapshot()`：读快照并重建 `DatabaseSchema`。
- `packages/sql/src/schema/DatabaseTable.ts:1304-~1450`，`toJSON()`：
  - 为了让元数据路径和内省路径序列化一致，里面已有大量归一化：类型名、`length`、`precision`、`default`、`extra` 小写、`primary`/`unique` 从索引推导，以及索引和外键的归一化。
  - 这是上游处理这类问题的既有手段。
- `packages/sql/src/schema/DatabaseSchema.ts:650-664`，`toJSON()`：负责排序和 `nativeEnums`。
- `DatabaseSchema.ts:152-`，`create()`：内省入口，会排除迁移表。
- `DatabaseSchema.ts:202-`，`fromMetadata()`：元数据路径。
- `packages/sql/src/schema/SqlSchemaGenerator.ts:82-93`，`getTargetSchema()`。
- sqlite 的内省实现在 `packages/sqlite` 下的 SchemaHelper，我没有展开读。

## 【3 并列与牵连】
- 并列写入点有 `create()`、`createInitial()` 和 `runMigrations()` 三处，只有最后一处走内省。
- `up` 和 `down` 共用 `runMigrations`，所以改这里会同时影响两者。
- 读取方是 `getSchemaDiff()`、`checkSchema()`、`create()` 和 `getPending()`，它们都依赖快照内容，因此快照一旦漂移，下一次 `migration:create` 会得到错误的 diff。
- 如果走"改归一化"的方向，`DatabaseTable.toJSON()` 会影响所有驱动：pg、mysql、mssql、oracle、sqlite 的快照测试和 `.snap` 文件。
- 如果走"`up` 后不用内省"的方向，影响的是 pg 等场景。`runMigrations` 注释和 `:243` 的测试说明"up 后从 DB 内省写入"是有意为之，大概是为了反映迁移里手写 SQL 的结果。
- `docs/docs/migrations.md:93-98` 写着两条路径"produce the same serialized shape"，且承认"some DB-specific details can still produce small diffs"。

## 【4 现有测试与约定】
`tests/features/migrations/Migrator.sqlite.test.ts`：
- `:103-150`：`up`/`down` 都应调用 `storeCurrentSchema`，断言 `toHaveBeenCalledTimes(1)` 和 `(2)`。
- `:152-186`：`storeCurrentSchema` 抛错时，`up`/`down` 仍应成功（只读文件系统）。
- `:188-221`（GH #7607）：`expect(afterUp).toEqual(afterCreate)`。这是最接近本题的既有断言，但只用了空的 memory 驱动配置和 blank 迁移，没有真实表，所以抓不到真实表的漂移。
- `:223-281`（GH #7234）：断言列字段键集合相同，布尔字段是真布尔，非复合主键的 `primary` 为 true。注释写着 up 路径"is now written from DB introspection"。

约定与冲突：
- 约定是两条路径必须序列化一致。
- 与题面不冲突：题面正是在说内省路径在 sqlite 上与元数据路径不一致。
- 隐藏测试很可能是 `afterUp` 对 `afterCreate` 的 `toEqual`，但这次带有真实实体，比如有默认值、索引、外键、枚举、布尔等。

## 【5 边界与隐含要求】
- sqlite 内省的常见差异点（推测，未验证）：
  - 类型别名和大小写（`integer`/`text`/`varchar(255)`、`datetime`）。
  - `default` 的引号和表达式形式。
  - 布尔列在 sqlite 里是 `integer`，`mappedType` 不同。
  - 外键 `updateRule`/`deleteRule`，以及索引名和唯一约束的表示。
  - `enumItems` 在 sqlite 里靠 check 约束表示。
  - `comment`、`collation`。
- 只修一个字段可能不够，需要对着实际 diff 逐项归一化。
- 同样要保证对 pg、mysql 等的既有快照不变。
- 保持 `catch` 吞错的语义。
- 事务上下文 `ctx` 要继续传入。
- 迁移里手写 SQL 的结果，是否要反映进快照，是个设计取舍。

## 【6 改动规模】
- 最小方案：改 `Migrator.ts` 一处，`up`/`down` 后不再用内省。
- 但这会改变既有行为，并可能让 #7234 一类的测试注释和断言失效。
- 另一种方案：在 `DatabaseTable.toJSON()` 补若干归一化，约 1 个文件几处。
- 另外要加或改 sqlite 测试，可能还要更新其他驱动的快照。
- 整体是局部修补，不需要新结构。

## 【7 难点一句话】
没有可见的复现和期望输出，难点是先判断快照里到底哪些字段在 sqlite 内省路径下漂移。还要在"`up` 后不再内省"和"补全序列化归一化"两种修法里选对，同时不破坏其他驱动的既有快照测试。