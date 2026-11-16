**档案：django__django-11964（TextChoices/IntegerChoices 的 `__str__`）**

**【1 题面要点】**
- 要求的行为：模型字段 `choices` 指向 `TextChoices`/`IntegerChoices` 时，新建实例上的属性值是枚举成员。对它调用 `str()` 得到 `'MyChoice.FIRST_CHOICE'`，而从数据库取回的实例得到 `'first'`。期望两者一致，即 `str(member)` 应返回成员的 value。
- 复现：有。题面给了 `MyChoice(TextChoices)` 模型和两个测试。
- 期望输出：有。失败信息是 `AssertionError: 'MyChoice.FIRST_CHOICE' != 'first'`。
- 修法建议：题面没有给。只有一句现象描述：“when invoking `__str__(...)` we don't actually get the value property of the enum value”。

**【2 相关代码】**
- `django/db/models/enums.py`：整个文件约 75 行。
  - `ChoicesMeta`（第 8 行起）：`__new__` 解析 `(value, label)` 元组，并给类加 `label` 属性。
  - `Choices(enum.Enum, metaclass=ChoicesMeta)`：第 `class Choices` 处，基类，目前只有 `pass`。
  - `IntegerChoices(int, Choices)`、`TextChoices(str, Choices)`：混入 `int`/`str`，没有重写 `__str__`。
- 根因：这里没有定义 `__str__`。`enum.Enum.__str__` 返回 `'ClassName.MEMBER'`，而 `str`/`int` 混入没有覆盖它，因为 MRO 里 `Enum` 在前面。
- 字段层不用动。字段不转换值，创建时保留原样的枚举对象；从数据库取回时就是普通的 str/int。

**【3 并列与牵连】**
- 并列实现：`Choices`、`IntegerChoices`、`TextChoices` 三个类。最稳妥的做法是在基类 `Choices` 上加一个 `__str__`，三者一起生效。
- `Choices` 还会被用于其他混入类型：`bytes`、`float`、`frozenset`、`date`、`datetime`、`time`、`timedelta`、`Decimal`、`ipaddress` 各类（见 tests/model_enums/tests.py:146-215）。基类上的 `__str__` 会作用于所有这些类型，所以返回 `str(self.value)` 比较合适。
- `django/db/migrations/serializer.py:49` 的 `ChoicesSerializer` 序列化 `self.value.value`，不依赖 `__str__`，不受影响。
- 其他可能受影响的地方：模板渲染、`'%s' % member`、f-string。`str.__format__` 对 str 子类会直接用 str 值，而 Enum 混入的 `__format__` 在不同 Python 版本行为不同（见 5）。
- 文档：`docs/ref/models/fields.txt` 约 190-300 行是枚举章节，`docs/releases/3.0.txt:87` 是发布说明。如果这是 3.0 的 bug 修复，可能还要补 release notes。

**【4 现有测试与约定】**
- `tests/model_enums/tests.py` 是现有测试，约 240 行。其中的断言：
  - `:46` `assertEqual(Suit.labels, [...])`
  - `:51` `assertEqual(Suit.DIAMOND.label, 'Diamond')`
  - `:58` `assertIsInstance(Suit.DIAMOND.label, Promise)`
  - `:235` `assertNotIn(None, choice_enum.labels)`
- 现有测试没有任何对 `str(member)` 的断言。没有现有测试会因此冲突，隐藏测试大概率是新增的 `str(Suit.DIAMOND) == '1'`、`str(YearInSchool.FRESHMAN) == 'FR'` 之类，也可能包含对模型实例创建后属性的断言。
- 约定：Python 标准库的 `enum` 在 `str` 混入时的行为，以及 `IntegerChoices`/`TextChoices` 的设计初衷（值等同于普通 int/str）。题面期望与这个设计一致，没有冲突。
- 仓库里没有可参考的现成实现。

**【5 边界与隐含要求】**
- 所有混入类型都要能 `str()`：`Decimal`、`date`、`bytes` 等。用 `str(self.value)` 对它们都有意义。
- `__format__`/`%s`/f-string：Python 3.8 以前对 mixin 枚举的 `format()` 用 value，3.8 起有变化。`str()` 改了之后，`'%s' % x` 是否一致，需要在仓库支持的 Python 版本上核对。
- `repr()` 不应变，仍是 `<Suit.DIAMOND: 1>`。
- `label` 属性、`choices`/`values`/`labels`、`__contains__` 不应被影响。
- 懒翻译（`Promise`）标签不进入 value，不受影响。
- `__empty__` 的处理逻辑不变。
- 创建后立即读取属性仍是枚举成员而非原始值。题面只要求 `str()` 一致，没要求类型一致，所以没必要改字段层。

**【6 改动规模】**
- 1 个文件、1 处实质改动：在 `enums.py` 的 `Choices` 上加一个 `__str__` 方法，约 3 行。
- 加测试约 1 个文件，几行。可选补文档/release notes。
- 属于局部补丁，不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
改动本身很小，难点在于找准位置：要把 `__str__` 放在 `Choices` 基类（不是 `TextChoices`/`IntegerChoices` 各一份），且返回 `str(self.value)` 才能覆盖所有混入类型。其次是确认 `__format__` 在支持的 Python 版本上是否也需要一并处理。

**说明**：这次只做了有限的查证。`__format__` 和支持的 Python 版本没有核实，档案里这部分是推测。