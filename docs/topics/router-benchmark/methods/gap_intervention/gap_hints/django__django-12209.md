## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名、但很可能也要一起处理的位置
1. `django/db/models/base.py` 的 `_save_table`(约 850–857 行):"有默认值的 pk 就强制 INSERT"的逻辑在这里。要弄清它在什么条件下触发,以及触发时 pk 是调用方显式给的,还是 `get_pk_value_on_save`(842–845 行)用默认值刚生成的,这两种来源目前没有区分。
2. `django/core/serializers/base.py` 约 223 行:`DeserializedObject.save` 调用 `save_base(raw=True)`,即 `loaddata` 的路径。题面提到 loaddata 重复加载 fixture 会出问题,需要和 `Model.save()` 一起验证。
3. `save()`/`save_base()` 对 `force_insert`、`force_update`、`update_fields` 的传递(base.py 663–830 行):看清这几个参数与上述强制 INSERT 分支如何交互,显式 `force_update=True` 不应被改动。
4. 多表继承路径(base.py 约 784、813 行,`parent_inserted`):父表保存也会走 `_save_table`。

B. 题面没给例子、但很可能被检查的输入/边界情况
- 新建实例(`_state.adding=True`)、pk 有默认值、调用方显式传 pk 且该行已存在:预期 UPDATE,不应报 IntegrityError。
- 同样的实例但该行不存在:UPDATE 影响 0 行后应回退到 INSERT。
- 不传 pk、靠默认值生成:这是原有的优化场景,不应多做一次无用的 UPDATE,需确认仍保持。
- pk 不是 UUID,例如 `tests/serializers/models/data.py:189` 的 BooleanField pk(默认值 False):注意 `self._meta.pk.default` 的真值判断(854 行)对 falsy 默认值的表现。

C. 仓库里已有的约定、文档或测试
- `docs/ref/models/instances.txt` 463–481 行(How Django knows to UPDATE vs. INSERT)规定:pk 已设置先 UPDATE,未命中再 INSERT,这是要遵守的行为约定。
- `tests/basic/models.py:48` 有现成的 uuid 主键加 `default=uuid.uuid4` 的模型;另看 `tests/basic/tests.py`、`tests/force_insert_update/tests.py`、`tests/serializers/tests.py` 中与 pk 默认值、强制 INSERT 相关的现有测试,确认不被破坏。
- 在 `tests/` 下 grep `_state.adding` 和 pk 带 default 的模型(如 `tests/model_formsets/test_uuid.py`、`tests/model_forms/models.py`),看有无依赖现行为的用例。

D. 提交前建议额外自测
1. 先 `create()` 一个对象,再用同 pk 新建实例并 `save()`:应为一次 UPDATE,字段被更新,不报错。
2. 用同样的 pk 对数据库里不存在的行 `save()`:应成功 INSERT。
3. 把同一份带显式 pk 的 fixture 通过 `loaddata` 或 `serializers.deserialize(...).save()` 加载两次,第二次不应失败;再用 `Model()` 不传 pk 保存,检查查询数没有多出 UPDATE。
