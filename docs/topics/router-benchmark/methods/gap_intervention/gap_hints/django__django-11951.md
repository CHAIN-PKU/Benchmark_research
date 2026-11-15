## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
1. `django/db/models/query.py` 的 `_batched_insert`（约 1205–1212 行）是 `bulk_create` 里实际算 batch_size 的地方。`bulk_create` 本身（438 行）只是把参数原样传下去，所以别在 `bulk_create` 里找错位置。
2. `bulk_create` 会分别调用 `_batched_insert` 处理 `objs_with_pk` 和 `objs_without_pk`（约 478、490 行）。两处调用的 `fields` 不同，`bulk_batch_size` 的返回值也就不同。核对改动对两条路径是否都生效。
3. `bulk_update`（约 522–523 行）已经有「取最小值」的写法。它是并列的参考实现，注意对比两处对 `max_batch_size` 的处理是否一致，尤其是 `_batched_insert` 里现有的 `max(..., 1)` 保护。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
1. `batch_size=None` 或 0：应走后端计算出的默认值，行为不能变。
2. 显式 `batch_size` 大于后端上限，例如 SQLite 的 `max_query_params // len(fields)`。此时应被压低到后端上限。
3. 显式 `batch_size` 小于后端上限：应保持用户给的值。
4. 后端 `bulk_batch_size` 的返回值可能为 0 或很小。看 `sqlite3/operations.py` 的 `bulk_batch_size`（`len(fields)==1` 时返回 500，`fields` 为空时返回 `len(objs)`）和 `oracle/operations.py`。`range` 的步长不能为 0。
5. 基类 `base/operations.py` 返回 `len(objs)`，即不限制。这时用户给的 batch_size 应该仍然有效。

**C. 仓库里已有的约定、文档或测试**
1. `tests/bulk_create/tests.py` 的 `test_explicit_batch_size`（约 189 行）和 `test_explicit_batch_size_efficiency`（约 209 行）。核对它们在改动后是否仍然成立。
2. `tests/bulk_create/tests.py` 里可能有针对 `bulk_batch_size` 的 mock 或 `override` 类测试，可以搜一下。
3. `docs/ref/models/querysets.txt` 里 `bulk_create` 的 `batch_size` 说明（约 2084 行）只写了「默认」行为，没写显式值与后端上限的关系。`bulk_update` 的说明（约 2125 行）可作对照。判断文档是否需要同步。

**D. 提交前建议额外自测的情况**
1. 用 mock 或 patch 把 `connection.ops.bulk_batch_size` 固定成一个小值，例如 2。传入更大的 `batch_size`，检查实际发出的 INSERT 次数和每批的对象数。
2. 同一个小上限下，传入更小的 `batch_size`，确认按用户的值分批。
3. 不传 `batch_size`，并且混合带主键和不带主键的对象。确认两条路径的行为都正确，已有的 `bulk_create` 测试也不退化。
