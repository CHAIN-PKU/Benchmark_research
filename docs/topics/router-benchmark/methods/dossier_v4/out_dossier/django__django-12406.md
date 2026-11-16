我已经查完关键位置，现在整理档案。

# 仓库档案：ModelForm 中 RadioSelect 对 blank=False 的 FK 不应出现空选项

## 【1 题面要点】
- 要求的行为：`ModelChoiceField`（由 FK 生成）配 `RadioSelect` 时，如果模型字段 `blank=False`，渲染新表单就不该出现 `---------` 这一项，也不该有被 checked 的 radio。
- 题面给了复现：`TestRun.data_file = ForeignKey(..., null=True, blank=False)`，`widgets = {'data_file': RadioSelect()}`。
- 题面给了当前输出：`<input checked="checked" id="id_data_file_0" ... value=""> ---------`。
- 期望输出只有一句话，没有完整 HTML：“there should be no checked option for RadioSelect's <input> tags when rendering a new form from a model if blank is not a valid selection.”
- 题面没有给修法建议。
- 标题和正文说的是“不显示空选项”，末句说的是“没有 checked 的选项”，两者不完全等价。

## 【2 相关代码】
- `django/forms/models.py:1184-1191`，`ModelChoiceField.__init__`：现在只有 `required and initial is not None` 时才把 `self.empty_label` 设为 `None`。否则保留默认 `"---------"`，与所用 widget 无关。
- `django/forms/models.py:1143-1165`，`ModelChoiceIterator`：`__iter__` 在 `empty_label is not None` 时先 yield `("", empty_label)`。`__len__` 和 `__bool__` 也依赖 `empty_label`。
- `django/db/models/fields/related.py:973-983`，`ForeignKey.formfield`：不传 `empty_label`，也不看 widget 或 blank。`required` 由 `Field.formfield` 按 `not self.blank` 设置（`fields/__init__.py:888-891`）。
- `django/forms/widgets.py:582-614`，`ChoiceWidget.optgroups`：把空值 `''` 的选项判为 selected。表单未绑定、value 为 `None` 时，`format_value` 返回 `['']`，所以空选项被选中，radio 就带上 `checked`。
- `django/forms/widgets.py:757-760`，`RadioSelect`：目前是空壳，只有模板和 `input_type`。
- `django/forms/widgets.py:669-700`，`Select`：有 `_choice_has_empty_value` 和 `use_required_attribute`，把空选项当作惯用写法。

## 【3 并列与牵连】
- `ModelMultipleChoiceField`（`models.py:1287-1299`）已经固定 `empty_label=None`，不受影响。
- `OneToOneField` 继承 `ForeignKey.formfield`，会自动一起生效。
- `django/contrib/admin/options.py:233` 在 `formfield_for_foreignkey` 里对 `radio_fields` 设 `kwargs['empty_label'] = _('None') if db_field.blank else None`。admin 已经对 radio 做了类似处理，可作参考。
- `reverse_related.py:118` 和 `fields/__init__.py:839 get_choices` 是 `BLANK_CHOICE_DASH` 的并列实现，用于普通 `ChoiceField`。题面只涉及 FK 的 `ModelChoiceField`，不一定要改。
- 改 `__init__` 的条件会影响所有 `ModelChoiceField(widget=RadioSelect)`，包括手写的非 ModelForm 字段，也会影响 `__bool__` 和 `__len__`。
- 同一个 widget 实例既可能传类，也可能传实例（`RadioSelect` 或 `RadioSelect()`），`widget` 参数在 `Field.__init__` 里才实例化。

## 【4 现有测试与约定】
- `tests/model_forms/test_modelchoicefield.py:132-140` 断言 `empty_label=None` 时 `bool(f.choices)` 为 True。删除数据后为 False；`empty_label='--------'` 时仍为 True。
- `test_modelchoicefield.py:179` 的 `ModelChoiceField(Category.objects.all(), widget=forms.RadioSelect)` 是 `required=True`，且 `initial` 为 None。该测试断言的是查询次数，不是选项，但会受影响。
- `test_modelchoicefield.py:347` 也用了 `RadioSelect`，看起来是 required 的字段，改动后选项数和 id 可能变化，需要复核。
- `docs/ref/forms/fields.txt:1175-1191` 把 `empty_label` 描述为 `<select>` 的行为。文档写了“required 且有 default initial 则不创建空选项”，这是现有的先例。
- 没有找到外部规范。唯一的约定是 admin 的 `radio_fields` 逻辑。
- 现有测试与题面期望不直接冲突，但可能有测试隐含地依赖 radio 里带空项，需要全量扫描。我没有做全量扫描。

## 【5 边界与隐含要求】
- 只在 `required=True`（即 `blank=False`）时去掉空项。`blank=True` 的 radio 仍需保留空项，否则无法取消选择。
- 显式传入的 `empty_label` 要保持有效。需要区分“用户没传”和“用户传了值”，现在默认值是 `"---------"` 字符串，无法区分。
- 显式 `empty_label=None` 与 required 的组合要保持原有语义。
- 判断依据是 widget 类型。要用 `isinstance`/`issubclass` 或给 widget 加属性，并考虑 `RadioSelect` 子类、传类和传实例两种写法。
- 已有 `initial` 的情况原本就没有空项，应保持不变。
- “没有 checked”这一点：空项去掉后，value 为 `None` 时不会有任何选项被选中，但要确认 `format_value(None)` 的结果 `['']` 不会误匹配到某个真实选项。
- `ModelChoiceIterator.__bool__` 在去掉空项后，空 queryset 的行为会变，需要确认没有副作用。
- 未绑定表单、绑定表单提交空值两种场景。后者应走正常的 required 校验报错。

## 【6 改动规模】
- 最小方案：改 `django/forms/models.py` 一个文件，一处（`ModelChoiceField.__init__` 的 empty_label 判定，约 3-5 行）。
- 完整方案：再加 `ForeignKey.formfield` 或 widget 的小改动，以及文档和测试，共 2-4 个文件。
- 属于局部修补，不用新增结构，也不贯穿多层。

## 【7 难点一句话】
代码量很小，难点在于判断“用户没传 `empty_label`”与“用户显式传了”的区分，以及把改动限定在 required 的 RadioSelect 上。这样才不会误伤 `blank=True` 的字段和已有测试（如 `test_modelchoicefield.py:347`）。