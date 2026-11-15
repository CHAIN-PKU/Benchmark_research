## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) ClassDocumenter 的 doc_as_attr 路径（import_object/get_doc/add_content，约1462-1471、1676-1732行）会丢掉文档注释，需确认各别名实际走哪个 documenter；2) DataDocumenter 与 AttributeDocumenter 的 add_content/update_content 成对，需一并核对；3) GenericAliasMixin/NewTypeMixin/TypeVarMixin 的 update_content 都无条件追加 'alias of'，对照 Documenter.add_content 看文档与默认文本的关系。
B. 1) 带文档与无文档别名并存，无文档的仍应显示 alias of；2) Dict/Union/Callable/NewType/TypeVar/指向类的别名逐一核对；3) autodata 与 autoattribute 两种场景，以及 #: 注释和下一行 docstring 注释。
C. 现有测试 tests/test_ext_autodoc_autodata.py、test_ext_autodoc_autoattribute.py、test_ext_autodoc.py(约1924-2034)、test_ext_autodoc_autoclass.py(约328) 里 alias of 的期望输出需保持不变；tests/roots/test-ext-autodoc/target/ 下已有夹具可参考；CHANGES 条目约定。
D. 1) 同模块混合带文档的 Dict/Union/Callable 别名和无文档别名，用 autodata 与 automodule 生成；2) 指向普通类的别名加下一行 docstring；3) 类内属性别名走 AttributeDocumenter，并跑现有相关测试确认无回归。
