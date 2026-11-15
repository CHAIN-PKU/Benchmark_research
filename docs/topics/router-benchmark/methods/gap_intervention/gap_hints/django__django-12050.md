## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) query.py resolve_lookup_value 里 list/tuple 共用分支，末尾统一用 tuple(...) 重建；2) 调用点 build_filter（约1258行）及后续 check_filterable/build_lookup、In 等 lookup 的 get_prep_lookup 不应再改类型；3) 该分支里 F 与非 F 的解析分成两处写，重构时保持一致。
B. 1) list 输入返回 list，tuple 输入返回 tuple；2) 含 F()/表达式元素的 list 和 tuple 仍逐个解析；3) 空 list、空 tuple；4) list/tuple 子类，尤其 namedtuple，重建方式可能与普通 tuple 不同（参考 query.py 中的 namedtuple 用法）。
C. 1) 搜索 tests/queries、tests/expressions、tests/lookup 中涉及 resolve_lookup_value 或带表达式的 list/tuple 过滤的现有测试，确认不被破坏；2) fields/__init__.py:874 另有 (list, tuple) 处理，核对是否相关；3) 找 tests 中类似 PickledField/BinaryField 的字段用于回归测试。
D. 1) filter(field=[1,2]) 与 filter(field=(1,2)) 传到 get_prep_value 的类型是否与输入一致；2) 列表含 F('x') 时解析后仍为 list 且 SQL 正确；3) 跑 queries、expressions、lookup 测试模块确认无回归。
