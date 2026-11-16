# 仓库档案：sphinx-doc__sphinx-8548（autodoc 继承的数据成员/属性文档）

## 【1 题面要点】
- 要求的行为：`:inherited-members:` 应该对继承来的属性（数据成员）生效。autodoc 现在用 `(namespace, attrname)` 作为键去缓存的 docstring（attr_docs）里查找，只查当前类的命名空间，不查基类的命名空间。
- 题面没有复现脚本、没有期望输出，也没有修法建议。
- 关键句：「autodoc searches for a cached docstring using (namespace, attrname) as search-key, but doesn't check for baseclass-namespace.」
- 所以期望行为只能自己推断：`Derived` 加 `:members: :inherited-members:` 时，继承自 `Base`、带 `#:` 注释文档的属性应该被列出并带上文档。

## 【2 相关代码】（均在 sphinx/ext/autodoc/ 下）
- `__init__.py:597-608`，`Documenter.add_content`：
  - 用 `key = ('.'.join(self.objpath[:-1]), self.objpath[-1])` 查 `analyzer.find_attr_docs()`。
  - 对继承属性，key 里是 `Derived`，而注释文档登记在 `Base` 下，所以查不到。
- `__init__.py:654-780`，`Documenter.filter_members`：
  - `:685` 的 `namespace = '.'.join(self.objpath)`，`:749` 的 `elif (namespace, membername) in attr_docs:` 同样只看当前类。
  - 继承属性走不到这个分支，`isattr` 和 `keep` 都会落到别的分支，无文档就被丢弃，除非开了 undoc-members。
  - `:669 is_filtered_inherited_member` 负责 `inherited-members=<类名>` 的过滤。
- `importer.py:254-318`，`get_class_members`：
  - `:310-316` 只把 `ns == 当前类` 的 attr_docs 补成 `INSTANCEATTR`，基类的 ns 不被考虑。
  - `:301-308` 沿 MRO 收集“仅注解”的成员，其 `class_` 记为 `cls`。
- `__init__.py:1586-1606`，`ClassDocumenter.get_object_members`：
  - 非 inherited 时靠 `m.class_ == self.object` 过滤。
  - 靠 `docstring=` 注入文档（`:715` 的 `ObjectMember.docstring` hack）。
- `__init__.py:2163-2181`，`UninitializedInstanceAttributeMixin.get_attribute_comment`：
  - 已经沿 `getmro(parent)` 用 `(qualname, attr)` 查各基类的 attr_docs，是现成的“查基类命名空间”的参考做法。
- `__init__.py:2221-2234`：`get_doc` 和 `add_content`。当 `object is UNINITIALIZED_ATTR` 时会把 `self.analyzer` 设为 None。
- `importer.py:195-241`，旧版 `get_object_members`，已被废弃，但仍有 attr_docs 的同类逻辑。

## 【3 并列与牵连】
- 有两处同名查找逻辑，都用当前类的 namespace：`add_content` 的 key，以及 `filter_members` 的 `(namespace, membername) in attr_docs`。两处很可能都要处理。
- `get_class_members`（新）和 `get_object_members`（旧，Documenter 基类，6.0 移除）并列，后者带 `RemovedInSphinx60Warning`，一般不必改。
- 其他用 attr_docs 的地方：
  - `autosummary/__init__.py:363` 和 `:693`，`(qualname, attr) in analyzer.find_attr_docs()`。
  - `autosummary/generate.py:274-275`。
  - 这些可能同样受影响，但题面只讲 autodoc。
- `analyzer` 对应的是被文档化类所在的模块（`self.real_modname`）。基类若在别的模块，就要用基类自己的 `ModuleAnalyzer.for_module`，`get_attribute_comment` 已有这种做法。
- 改 `get_class_members` 会同时影响非继承场景（`m.class_ == self.object`）和 `autodoc-skip-member` 事件的参数。

## 【4 现有测试与约定】
- `tests/test_ext_autodoc.py:617-625`：`test_autodoc_inherited_members` 只断言 method 行，如 `'   .. py:method:: Derived.inheritedmeth()'`，没有属性。
- `:629-637` 和 `:641-649` 是 `inherited-members` 带类名、带 `None` 的用例。
- `tests/roots/test-ext-autodoc/target/inheritance.py` 里的 `Base` 和 `Derived` 目前没有任何带 `#:` 的属性。隐藏测试很可能往这里加属性，并断言类似 `.. py:attribute:: Derived.attr` 的输出。
- `tests/test_ext_autodoc_autoclass.py` 里没有 inherited 或 attr_docs 相关断言。
- 约定：属性文档就是 `#:` 注释，由 `ModuleAnalyzer` 以 `(类名, 属性名)` 为键记入 `attr_docs`。仓库内没有别的外部规范。
- 与题面不冲突，只是现有测试没覆盖。

## 【5 边界与隐含要求】
- 基类在另一个模块时，必须用基类模块的 analyzer，而不能只用当前的 `self.analyzer`。
- 多层继承：要沿 MRO 查找，并且子类覆盖时要取最近的一个。
- 嵌套类的 `qualname`（`Outer.Inner`）要和 attr_docs 的 key 对得上。
- 没有 `:inherited-members:` 时，继承属性不能出现（`class_`/`directly_defined` 的判断要保持正确）。
- 带类名的 `inherited-members: Base` 要能把 Base 及其上的属性排除掉，`is_filtered_inherited_member` 里 `name in cls.__dict__` 和 `__annotations__` 的判断对仅有注释文档的属性不成立。
- 私有属性（`_x`）、`:undoc-members:`、`:private-members:` 的组合。
- 实例属性（`self.x = 1  #: doc`）定义在基类 `__init__` 里。
- 注解形式（`x: int  #: doc`）和 `__slots__`。
- `add_content` 里 `UNINITIALIZED_ATTR` 会清掉 analyzer，要小心和新逻辑冲突。
- 基类的 analyzer 可能抛 `PycodeError`（如 C 扩展或内置类），要捕获。
- 同名属性被子类重新赋值但没写注释时，应该用哪边的文档。

## 【6 改动规模】
- 主要改 1 个文件，`sphinx/ext/autodoc/__init__.py`，可能加上 `importer.py`。
- 预计 2-4 处：
  - `add_content` 的 key 查找。
  - `filter_members` 的 attr_docs 判断。
  - 可能还有 `get_class_members` 里的 attr_docs 补充。
- 都是局部修补，不需要新增结构，但要新写一段沿 MRO 找基类 analyzer 的逻辑，或者抽成辅助函数。
- 测试和 fixture 另外加。

## 【7 难点一句话】
题面只有一句话、没有期望输出，要自己判断“继承属性文档”要在 `add_content`、`filter_members` 和 `get_class_members` 这几个互相牵连的查找点上用基类命名空间，还要处理跨模块基类、多层继承和 `inherited-members=类名` 的过滤，才能让隐藏测试通过。