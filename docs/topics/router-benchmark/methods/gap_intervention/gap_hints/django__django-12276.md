## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但可能要一起处理的位置**
1. `django/forms/widgets.py` 的 `ClearableFileInput`（约第 454 行）已有 `use_required_attribute`。逻辑挪到 `FileInput` 后，子类里的重复实现怎么处理要想清楚；`AdminFileWidget`（`django/contrib/admin/widgets.py:101`）继承自 `ClearableFileInput`，要确认行为不变。
2. 调用点在 `django/forms/boundfield.py:224`，传入的是 `self.initial`。要看清楚「initial 存在」在这里是什么值（`FieldFile`、字符串还是 `None`）。
3. `FileField` 默认 widget 是 `ClearableFileInput`（`fields.py:541`），`ImageField` 也是文件类字段。单独使用 `forms.FileInput` 才是题面重点。

**B. 可能被检查的输入/边界**
1. initial 为 `None`、空字符串、空的 `FieldFile`、有值的 `FieldFile` 或字符串，分别核对 `required` 是否输出。
2. `required=False` 的字段和 `Form.use_required_attribute=False` 不应受影响。
3. 基类 `Widget.use_required_attribute`（第 275 行）的返回值会与 initial 条件组合；`FileInput` 没有 initial 时仍要输出 `required`。

**C. 仓库里已有的约定、文档和测试**
1. `tests/forms_tests/widget_tests/test_clearablefileinput.py:153` 的 `test_use_required_attribute` 有注释说明「initial 存在时不要 required」的理由；`test_fileinput.py` 目前没有对应测试。
2. 文档 `docs/ref/forms/widgets.txt:318` 描述了 `use_required_attribute(initial)`，看是否需要补充，以及 `docs/releases/` 下是否需要加说明。
3. `test_textinput.py:77` 展示了这类测试的写法，可参考。

**D. 提交前建议自测**
1. 直接对 `FileInput` 调用 `use_required_attribute(None)` 和 `use_required_attribute('resume.txt')`，期望分别为 True 和 False。
2. 用 `forms.FileField(widget=forms.FileInput)` 建表单，传 `initial` 和不传 `initial` 各渲染一次，检查 HTML 里有没有 `required`。
3. 跑 `forms_tests` 里 widget 相关测试和 admin widgets 相关测试，确认 `ClearableFileInput` 和 `AdminFileWidget` 没有退化。
