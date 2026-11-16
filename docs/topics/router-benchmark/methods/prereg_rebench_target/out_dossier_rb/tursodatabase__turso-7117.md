【1 题面要点】
- 期望行为：把 AUTOINCREMENT 列用 `ALTER TABLE t ALTER COLUMN a TO a2 TEXT` 改成普通 TEXT 列后，`sqlite_sequence` 里不应再留下表 `t` 的陈旧行。
- 题面自己也承认：“unsure of alter column rules… not able to find any docs”。
- 复现：`CREATE TABLE t(a INTEGER PRIMARY KEY AUTOINCREMENT, b TEXT); INSERT ... ('x'),('y'); ALTER ... a TO a2 TEXT; SELECT * FROM sqlite_sequence;`。
- 实际输出：`t | 2`，而表的 SQL 已变成 `CREATE TABLE t (a2 TEXT, b TEXT)`。
- 期望输出没有明写，只能从“shouldn't be a stale sqlite_sequence”推断出 sqlite_sequence 里没有 `t` 行。
- 没有给修法建议，Interface 写“no new interfaces”。
- 没提 `sqlite_sequence` 这张表本身要不要保留。题面期望的只是去掉行，表本身留着（SQLite 的做法也是保留）。

【2 相关代码】
- `core/translate/alter.rs:1564-2055`：`AlterColumn` 和 `RenameColumn` 共用一个分支。
  - `1572` 是 AlterColumn 的解析；`1594` 用 `btree.get_column(from)` 取出旧列。
  - `1606-1624` 拒绝 PRIMARY KEY 和 UNIQUE 约束。
  - `1626-1653` 计算 `rewrites_physical_layout`（只看是否变成生成列、虚拟性变化、affinity 变化）。
  - `1851-1913` 用 `cursor_loop` 遍历 sqlite_schema，调用 `Func::AlterTable(AlterColumn)` 改写 SQL。
  - `2042-2054` 发出 `SetCookie` 和 `Insn::AlterColumn`。
- `core/vdbe/execute.rs:8462-…`：`op_function` 里 AlterColumn / RenameColumn 的 SQL 改写。
  - `8582` 的 `*column = column_def.clone()` 直接用新定义替换整列。
  - AUTOINCREMENT 在 SQL 中属于列约束，所以新列定义 `a2 TEXT` 里没有它，主键也一并丢了。
- `core/vdbe/execute.rs:12917`：`op_alter_column`，修改内存 schema（`btree` 的列）。
  - 我没读到它是否更新 `btree.has_autoincrement`，需要核对。
  - `core/schema.rs:2630` 定义 `has_autoincrement`，`2696` 从 characteristics 还原，`2946` 在生成 SQL 时用到。
- 参考实现：`core/translate/schema.rs:2243-2295` 是 DROP TABLE 清理 sqlite_sequence 的字节码：`Rewind` 遍历、`Ne` 比较名字、`Delete`、`Next`。
- 参考实现：`core/translate/alter.rs:156-250` 的 `emit_rename_sqlite_sequence_entry`，用于 RENAME TABLE，在 `1499` 处被调用。结构与上一条类似，可以照搬。

【3 并列与牵连】
- 并列分支是 `RenameColumn`：它与 AlterColumn 共用代码，但 RENAME 不改约束，AUTOINCREMENT 保留，不应删除 sqlite_sequence 行。
- 并列场景：ALTER 是否去掉了 AUTOINCREMENT，要在翻译期用旧列和新定义判断。旧列是 rowid alias 且表 `has_autoincrement`，新定义不再是它。
- 同类问题：DROP COLUMN 删除 AUTOINCREMENT 列时，也可能留下 sqlite_sequence 行。但该列是主键，通常不允许删，需要核对 `op_drop_column`（execute.rs:12744）。
- 牵连：一旦 AlterColumn 去掉了 PRIMARY KEY，rowid 别名关系也变了，涉及 `Column::try_from` 以及内存 schema 中的 `has_autoincrement`、`is_rowid_alias` 和主键标志。
- 牵连：`emit_rewrite_table_rows` 在改写物理布局时，可能需要把原来的 rowid 别名列写进记录，因为 a 不再是 rowid 别名。这块我没细看。
- MVCC：AUTOINCREMENT 在 MVCC 下不被支持（`core/mvcc/database/tests.rs:9047`），所以只需处理 WAL 模式。但 `emit_rename_sqlite_sequence_entry` 里有 MVCC 的 Delete，复制时可以保持一致。

【4 现有测试与约定】
- `testing/sqltests/turso-tests/alter_column.sqltest` 是现有 ALTER COLUMN 测试，格式为 `test name { SQL } expect { rows }`。
  - `:14-26` 的 `fail-alter-column-primary-key` 和 `fail-alter-column-unique` 都是 `expect error`。
  - 没有任何用例涉及 AUTOINCREMENT 或 sqlite_sequence，仓库里也没有 ALTER COLUMN 相关的 Rust 集成测试（tests 目录里 `ALTER COLUMN` 零匹配）。
- `tests/integration/query_processing/test_alter_table_reopen.rs:49-51` 断言 `SELECT name, seq FROM sqlite_sequence WHERE name = 't'` 得到 `[("t", 3)]`，那是 reopen 的场景。
- 隐藏测试很可能写成 sqltest，如 `SELECT * FROM sqlite_sequence` 期望空结果，或写成 Rust 的 `exec_rows`。
- 约定：DROP TABLE 的注释是 “if drops table, sequence table should reset”，即删行不删表。
- 外部规范：SQLite 本身不支持 `ALTER COLUMN`，这是 Turso 扩展，没有标准可对照。
- 与题面期望没有冲突。

【5 边界与隐含要求】
- 删除的行必须只匹配本表名，要用 normalize_ident 后的名字，不影响其他表的行。
- 仅当旧列确实是 AUTOINCREMENT 列时才删；对普通表、没有 sqlite_sequence 的库不能报错。
- 新定义里仍保留 `INTEGER PRIMARY KEY AUTOINCREMENT` 的情况：`1606` 的检查会拒绝带 PRIMARY KEY 的定义，所以这种情况进不来。
- 仅改类型但不去掉主键怎么办，题面没写。例如 `ALTER COLUMN a TO a INTEGER`，这同样丢掉 PK 和 AUTOINCREMENT，同样要清行。
- 内存 schema 的 `has_autoincrement` 要同步清掉，否则后续 INSERT 会走 AUTOINCREMENT 路径，或再次生成带 AUTOINCREMENT 的 SQL。
- 重开数据库后，sqlite_sequence 里不应出现 `t` 行。
- 事务回滚后，被删除的行应恢复（stmt_journal 相关，`core/translate/stmt_journal.rs` 提到 sqlite_sequence）。
- 同一连接上 prepared statement 的 schema 版本变化。

【6 改动规模】
- 主要改 `core/translate/alter.rs` 一个文件，可能再加 `core/vdbe/execute.rs`（`op_alter_column` 同步 `has_autoincrement`）。
- 大约 2 个文件、3 到 4 处。核心是在翻译期判断“AUTOINCREMENT 被去掉”，并发出一段类似 `emit_rename_sqlite_sequence_entry` / DROP TABLE 的删除字节码。
- 局部修补，不需要新增结构，也不贯穿多层；若要重构删除逻辑为公共函数，会稍多一点。
- 测试：新增 sqltest，也可能补 Rust 测试。

【7 难点一句话】
- 代码改动本身不大。难点在于：先确认 ALTER COLUMN 之后内存 schema 和实际 rowid 布局是否一致（`has_autoincrement` 和物理行布局都可能陈旧）；再把 DROP TABLE 的 sqlite_sequence 删除字节码正确搬进一个 AlterColumn/RenameColumn 共用的分支里，并只在 AlterColumn 且去掉 AUTOINCREMENT 时触发。