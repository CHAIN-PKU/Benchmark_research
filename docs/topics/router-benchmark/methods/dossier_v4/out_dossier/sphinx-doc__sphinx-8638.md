**档案：sphinx-doc__sphinx-8638（实例变量被自动链接到同名变量）**

调查依据：读了 `sphinx/domains/python.py` 的相关段落、`sphinx/util/docfields.py`，并 grep 了测试目录。没有运行代码，也没有用 git（快照不是 git 仓库）。

**【1 题面要点】**
- 期望行为：类里记录的实例变量（以及任何变量）不应自动链接到项目里其他同名变量。原文是 “That the class variable documentation not be linked to any other.”
- 用户可以自己写 “see :const:`somename`” 来手动引用。
- 题面没有给期望输出，也没有修法建议。
- 复现步骤是外部仓库 `13steinj/sphinx-issue-examples`，分支 `referenced_variables`。题面承认自己没法在示例仓库里稳定复现 `limit` 的情况，现象是“有时才发生”。
- 题面没有说明链接到底出在哪个位置，需要自己定位。

**【2 相关代码】**
- `sphinx/domains/python.py:357-360`：`PyObject.doc_field_types` 里的 `PyTypedField('variable', rolename='obj', names=('var','ivar','cvar'), typerolename='class', typenames=('vartype',))`。
  - `:ivar name:` / `:var:` / `:cvar:` 字段的参数名会用 `rolename='obj'` 生成 `pending_xref`。
  - 这是我认为最可能的根因：字段里的变量名本不该被当作引用。
- `python.py:267-284`：`PyXrefMixin.make_xref` 对所有字段 xref 强制加 `refspecific=True`，并写入 `py:module` 和 `py:class`。
- `python.py:1125-1179`：`PythonDomain.find_obj`。
  - `searchmode==1`（refspecific）时，先精确匹配，不中再走 "fuzzy" 分支：`oname.endswith('.'+name)`（行 1158-1162）。
  - 这解释了题面说的“跨子包、跨类、有时才发生”：fuzzy 匹配会命中任意以 `.name` 结尾的对象。
- `python.py:1181-1205`：`resolve_xref` 调用 `find_obj`，最终 `make_refnode`。
- `sphinx/util/docfields.py:83-99`：`Field.make_field` 里的参数名 xref。
- `docfields.py:172-204`：`TypedField.make_field`，`handle_item` 在行 176 用 `self.rolename` 生成参数名 xref。

**【3 并列与牵连】**
- `GroupedField.make_field`（`docfields.py:129`）和 `Field.make_field`（`docfields.py:89`）也用 `rolename` 生成参数名 xref。
- `PyField` / `PyGroupedField` / `PyTypedField`（`python.py:310-333`）都继承 `PyXrefMixin`，行为一致。
- `parameter` 字段（`python.py:352`）没有 `rolename`，所以参数名不生成链接。`variable` 字段是唯一给参数名设 `rolename='obj'` 的 typed 字段，这是它的特殊之处。
- 如果改的是 `rolename`，会影响所有使用 `:var:`、`:ivar:`、`:cvar:` 的文档。napoleon 会生成 `:ivar:`（`tests/test_ext_napoleon_docstring.py:1623`），受影响。
- 如果改的是 `find_obj` 的 fuzzy 逻辑，影响面大得多：`:any:` 角色（`resolve_any_xref`，行 1215）、所有带 `.` 前缀的角色，以及类型字段都会受影响。
- C/C++/JS 域有各自的 `find_obj` 和字段定义，不是并列的必改项。
- 我没有查 `autodoc` 对 attribute 的输出，也没查 `py:data` / `py:attribute` 指令自己的签名是否会生成 xref。

**【4 现有测试与约定】**
- `tests/test_domain_py.py:183-206`：`test_domain_py_find_obj`，只测 `searchmode=0` 的精确匹配，例如 `find_obj(None, None, 'NONEXISTANT', 'class') == []`。没有 fuzzy 和 refspecific 的测试。
- `tests/test_domain_py.py` 里的 `pending_xref` 断言集中在类型注解解析，例如 `assert_node(doctree[0], pending_xref, refdomain="py", reftype="obj", reftarget="None")`（行 294）。我没找到断言 `:ivar` 字段参数名是 `pending_xref` 的测试。
- 带 `:ivar` 的测试 fixture 是 `tests/roots/test-root/objects.txt:97-99`（`:ivar int hour:`、`:ivar minute:`、`:vartype minute: int`）和 `tests/roots/test-ext-viewcode/objects.rst:71-73`。
- 没有 `process_field_xref` 在 Python 域的覆盖；只有 C、C++ 和基类（`domains/__init__.py:311`）有。
- 没发现与题面期望冲突的现有断言，但我没逐个翻 `test_build_html` 之类的 HTML 期望文件，可能有对 `:ivar` 生成链接的断言。
- 外部规范：Sphinx 文档对 `:ivar` 字段说明的行为我没核查。

**【5 边界与隐含要求】**
- 变量名是否仍需保留可点击能力：期望是不链接，但 `:vartype:` 的类型仍应保持链接。
- `:var` / `:ivar` / `:cvar` 三个名字应一致处理。
- `can_collapse` 的单项折叠路径和多项列表路径都要覆盖（`docfields.py:196-202`）。
- 若走 `rolename=None` 的修法，`Field.make_xref`（`docfields.py:66-67`）返回 `contnode or innernode(target, target)`，文本样式仍是 `literal_strong`。
- 隐藏测试可能断言字段里不再出现 `pending_xref`，也可能断言渲染结果不含链接。具体形式未知。
- 不要破坏精确匹配或带模块限定名的合法链接。

**【6 改动规模】**
- 最小修法：只改 `python.py:357` 那一处（去掉 `rolename='obj'`），1 个文件 1 处。
- 如果隐藏测试要求保留 `pending_xref` 但不 fuzzy 解析，则要改 `find_obj` 或 `resolve_xref`，是局部修补，不需要新增结构。
- 可能还要补测试和 CHANGES，这不算核心改动。

**【7 难点一句话】**
难在定位：题面没点出根因，现象“有时才链接”，需要看出是 `:ivar` 字段参数名带 `rolename='obj'` 加上 `refspecific` 的 fuzzy 后缀匹配；代码改动本身很小，但“只去掉变量名链接”和“收紧 fuzzy 匹配”两条路径的取舍要靠对隐藏测试的猜测。