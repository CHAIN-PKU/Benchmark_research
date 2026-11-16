**档案：django__django-12304（枚举类型在模板中不可用）**

**【1 题面要点】**
- 要求的行为：`{% if student.year_in_school == YearInSchool.FRESHMAN %}` 这样的模板写法要能工作。
- 原因：`YearInSchool` 是类，所以是 callable。模板变量解析会无参调用它，缺少必需的 `value` 参数，调用失败。
- 题面没有给复现代码和期望输出，只有上面这个模板片段。
- 修法建议（原句）：“The easy solution would be to declare do_not_call_in_templates = True on the various Choices classes.”

**【2 相关代码】**
- `django/db/models/enums.py:8-34` 的 `ChoicesMeta.__new__`：元类，创建枚举类并附加 `_value2label_map_` 和 `label`。
- `enums.py:61` 的 `Choices(enum.Enum, metaclass=ChoicesMeta)`，以及 `IntegerChoices`（72）、`TextChoices`（77）：公共基类和两个具体子类。
- `django/template/base.py:851-866` 的 `Variable._resolve_lookup`：
  - `callable(current)` 后先检查 `getattr(current, 'do_not_call_in_templates', False)`，为真就 `pass`，不调用。
  - 否则检查 `alters_data`，再尝试无参调用。
  - 这里不用改，是现成机制。

**【3 并列与牵连】**
- 并列实现：`Choices`、`IntegerChoices`、`TextChoices` 都继承自 `Choices`，在基类或元类上设一次即可覆盖。
- 通过 `models.Choices` 加自定义混入类型的写法（`docs/ref/models/fields.txt:275`）也走同一个元类。
- 函数式 API（`models.TextChoices('MedalType', ...)`）同样走元类，所以也被覆盖。
- 同类先例是 `related_descriptors.py:573,862` 和 `contenttypes/fields.py:540`，它们都用 `do_not_call_in_templates = True`。
- 影响面：只影响模板里对枚举类本身的解析。枚举成员（实例）不是 callable，不受影响。

**【4 现有测试与约定】**
- `tests/model_enums/tests.py` 是 `SimpleTestCase`，只有枚举本身的断言，没有模板相关测试。例如：
  - `:50` `repr(Suit.DIAMOND) == '<Suit.DIAMOND: 1>'`
  - `:45` `Suit.choices == [...]`
  - `:56` `assertIsInstance(Suit, type(models.Choices))`
- `tests/template_tests/test_callables.py:72,85,104` 有 `do_not_call_in_templates` 的约定测试。
- `docs/ref/templates/api.txt:339-344` 是该属性的文档。
- 与题面没有冲突。
- 隐藏测试很可能：
  - 在 `model_enums/tests.py` 里用 `Template`/`Context` 渲染 `{% if x == YearInSchool.FRESHMAN %}`。
  - 或者断言 `Choices` 类带有 `do_not_call_in_templates`。

**【5 边界与隐含要求】**
- 陷阱：在 `Choices` 的类体里直接写 `do_not_call_in_templates = True` 会被 `enum` 当成枚举成员。
  - 这会破坏 `choices`/`names`/`values`，也会在 `IntegerChoices` 上出问题，还会让 `@enum.unique` 抛错。
  - 所以要放到元类里：在 `__new__` 里给 `cls` 赋值，或者在元类上用属性。
- 要确认枚举成员本身访问该属性时不出问题，也不能新增成员，`names`/`choices` 不能变。
- Python 3.9 的 `enum` 在 `__new__` 之后给类设属性是可行的（现有的 `cls.label = property(...)` 就是这样做的）。
- 可能的缺口：文档和发布说明。

**【6 改动规模】**
- 核心：1 个文件（`enums.py`），1-2 行。
- 可选：加测试，补文档。
- 属于局部修补，不需要新增结构。

**【7 难点一句话】**
改动本身很小，难点是避开 `enum` 把类体属性当成成员的陷阱，要把属性设在元类或类对象上，而不是写在类体里。