## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
1. `django/forms/models.py` 的 `ModelChoiceField.__init__`（约 1184–1191 行）。`empty_label` 在这里决定。`ModelChoiceIterator.__iter__`（约 1149 行）只看 `empty_label is not None`，它是空选项的唯一来源。先弄清空选项是在哪一层产生的，再决定改哪里。
2. `ModelChoiceField` 在构造时就已经拿到 `widget` 参数，而 `Meta.widgets` 会经由 `formfield()` 传入，所以构造时能看到 widget。要核对 widget 可能是类也可能是实例，以及 `Field.__init__` 里 widget 被实例化的时机。
3. `ModelMultipleChoiceField`（约 1299 行附近）以及 `ForeignKey.formfield`（`django/db/models/fields/related.py` 约 973 行）。核对它们是否会受影响，也就是 `blank=True`、`required=False` 时的行为。
4. `RadioSelect` 在 `django/forms/widgets.py` 约 757 行，只是 `ChoiceWidget` 的子类。核对其他选择类 widget（`Select`、`CheckboxSelectMultiple`、`NullBooleanSelect`）不要被误伤。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
1. `blank=True`（也就是 `required=False`）的外键配 `RadioSelect`。此时空选项应当保留，因为这是合法选择。
2. 非 RadioSelect 的 widget，也就是默认 `Select`。即使 `blank=False`，空选项仍应保留。
3. 同时有 `initial` 或 `default` 的情形。已有逻辑是 required 且 initial 非 None 时 `empty_label=None`。新逻辑与它的叠加要核对。用户显式传入的 `empty_label` 也要核对：显式传 `None` 或自定义文本时，行为是否合理。
4. 题面要求新建表单时 `RadioSelect` 没有任何被选中的 input。渲染结果里不应再出现 `checked`，也不应出现 value 为空的 radio。要同时检查 `bound` 和 `unbound` 两种表单。

**C. 仓库里已有的约定、文档或测试**
1. `docs/ref/forms/fields.txt` 约 1175–1191 行记录了 `empty_label` 的语义，包括 required 且有 initial 时不创建空选项。新增行为如果改变了语义，要核对文档是否需要同步说明。
2. 查 `tests/model_forms/`、`tests/forms_tests/` 里关于 `empty_label`、`RadioSelect` 和 `ModelChoiceField` 的现有测试，别让它们回归。重点看 `ModelChoiceIterator` 的 `len` 和 `bool` 逻辑（约 1162、1165 行）对空选项的依赖。
3. `Select.use_required_attribute`（`widgets.py` 约 689 行）依赖第一个选项是否为空值。`ChoiceWidget` 也有类似约定。核对 `RadioSelect` 的 required 属性渲染有没有被牵连。

**D. 建议提交前额外自测的情况**
1. `blank=False` 的 FK 配 `RadioSelect`：渲染后没有空选项，也没有 checked。
2. `blank=True` 的 FK 配 `RadioSelect`，以及 `blank=False` 的 FK 配默认 `Select`：两者都仍有 `---------`。
3. 跑 `model_forms` 和 `forms_tests` 两个测试套件，确认没有回归。再额外试一次表单有 instance、已有选中值时的渲染。
