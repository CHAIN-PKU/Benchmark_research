# 第 6 批归因（6 题）

## 1. gin-gonic__gin-3227
1. 题目要什么：RedirectTrailingSlash=false、RedirectFixedPath=true 时，请求 /ping/ 不应被重定向（应 404）。
2. 标准答案：改的是路由树 tree.go（给节点加 static 类型，访问到 path=="/" 的静态节点时设 value.tsr=true）。与题面说的 gin.go 传参问题完全不是同一处，修的是"带参数路由的尾斜杠建议（tsr，trailing slash recommendation）判断漏了"。
3. DS 两次改法几乎一样：gin.go 里 redirectFixedPath(..., engine.RedirectFixedPath) 改成传 engine.RedirectTrailingSlash，并改了 routes_test.go 老断言（run1 加 404 断言 + 打开开关后再测；run2 直接把期望改为 404）。两次都挂在 TestRedirectTrailingSlash（隐藏测试 tree_test.go:703 "want true, is false"）。没有一过一挂。
4. 挂因：隐藏测试测的是 node.getValue("/hello/abx/") 对 /hello/:name 系列路由应返回 tsr=true，是 tree 层 bug；DS 按题面把 gin.go 的传参修了，题面描述的现象确实修了（DS 复现返回 404），但测试要的是另一处。证据：gold 只改 tree.go；test_patch 只加 tree_test.go 的用例；DS 补丁完全没碰 tree.go。
5. 主类别 E（题面期望与隐藏测试不一致）；副 D（DS 还改了旧测试 TestRouteRedirectFixedPath 的老断言，虽然未被判为 P2P 失败，P2P 为空）。
6. 动手前信号：看不出（题面指向 gin.go#L421，仓库里按题面修是自然的；没有提示 tree.go 的尾斜杠判断有 bug）。
7. 把握：高。

## 2. preactjs__preact-3345
1. 题目要什么：effect（副作用）清理函数抛异常时，组件卸载不能半途中断（后续清理函数要继续执行，DOM 不留垃圾）。
2. 标准答案：hooks/src/index.js 两处：options.unmount 里对每个 hook 单独 try/catch，记录错误，循环完再统一 _catchError；invokeCleanup 里调用前先把 hook._cleanup 置空，防止抛错后被重复调用。
3. run1（挂）：81 轮，改了 hooks 的 unmount 循环（逐个 try/catch，还加了 isProcessingException 辅助函数），并改 src/diff/index.js 的 unmount 加多层 try/catch；没有清空 _cleanup。挂在 "handles errors correctly"：expected spy called exactly once, but called twice（useEffect.test.js 第 1650 行附近，某个清理/effect 被重复调用）。run2（过）：只改 invokeCleanup 一处，先清空 hook._cleanup 再调用，36 轮，17 个测试全过。
4. 挂因：run1 漏了"清理函数调用前先置空，避免重复调用"这一半；改动大且发散（改核心 diff 代码）。证据：run1 补丁无 _cleanup=undefined；run2 补丁只有这一处就通过。关于环境：DS 自述无 node_modules、跑不了 Karma，只能用自制 Node 脚本验证；但评分阶段 Karma+Chrome Headless 151 正常运行并给出了明确的断言结果，所以不是环境问题，只是 DS 本地无法跑真测试（run1 没验证出重复调用）。
5. 主类别 C（成对的另一半漏改：逐个捕获 + 清空已执行的清理）；副 F 仅限"DS 沙箱里跑不了 Karma 导致验证不到位"，不是判错原因。
6. 动手前信号：弱。题面写了"后续清理函数不被调用"；仓库里 invokeCleanup 可见，但"重复调用"要靠推演（抛错后卸载时同一个清理会再被调一次）。算"看不出/很弱"。
7. 把握：高（有一过一挂对照，差异就在 _cleanup 置空）。

## 3. projectlombok__lombok-3371
1. 题目要什么：record 里 `byte @NonNull[] bytes`（类型注解写在数组上）也要在紧凑构造器里生成空检查。
2. 标准答案：javac 和 eclipse 两个 HandleNonNull 里，若注解父节点是 TYPE_USE 则再上一层取字段节点；用统一的 node 处理。隐藏测试 NonNullOnRecordTypeUse：`@NonNull int[] a, int @NonNull [] b, int[] @NonNull [] c`，只对 a、b 生成检查，c（注解挂在内层数组维度）不生成。
3. run1（过）：124 轮，javac 里在 TYPE_USE 分支加字段 record 判断，复用原有"只认顶层类型注解"检查，所以 c 被正确排除。run2（挂）：91 轮，直接把 TYPE_USE 父节点的字段都当 @NonNull 字段，挂在 javac-NonNullOnRecordTypeUse：实际输出多生成了 `if (c == null) throw ...`（期望里没有）。
4. 挂因：run2 没区分"注解挂在顶层数组 vs 内层维度"，对 `int[] @NonNull [] c` 也生成了空检查。证据：测试输出 "expected:<}> but was:<if (c == null) {"。run1 因保留了原 TYPE_USE 分支里对顶层注解的校验而通过。另两个 P2P 都过；另有 4~8 个 With/Builder 等记录测试在基线上就失败，两次相同，不计。
5. 主类别 G（精确边界：嵌套数组维度上的注解不该触发）；副 A（题面只有一个简单场景，真修法要考虑更多形状）。
6. 动手前信号：弱。仓库里 eclipse 的 TYPE_USE 分支已有 getTopLevelTypeReferenceAnnotations 顶层检查，暗示要区分层级；题面本身看不出。
7. 把握：高。

## 4. sphinx-doc__sphinx-11510
1. 题目要什么：source-read 事件的修改要对 `.. include::` 的被包含文件也生效。
2. 标准答案：在 sphinx/directives/other.py 的 Include.run 里临时替换 state_machine.insert_input，把被包含文本拼回字符串，触发已有的 source-read 事件（docname 用被包含文件的文档名），再拆回行，保留 docutils 末尾 2 个标记行。仅在有 source-read 监听器时启用。
3. 两次都不同于标准答案，都新增了一个 `include-read` 事件（run1 104 轮：拦截 insert_input 触发新事件，参数为列表单元素；run2 96 轮：替换 docutils FileInput 触发新事件，参数为行列表），并改文档/CHANGES。两次都挂在两个 F2P：test_include_source_read_event（'baz/baz' 不在上报的 source 里）和 ..._nested_includes（'The #magical foo.' != 'The amazing foo.'）。无一过一挂。
4. 挂因：测试用 app.connect("source-read") 监听，期望 include 文件也触发 source-read；DS 自创新事件，source-read 仍不触发，等于没解决用户场景（用户扩展本来就连的是 source-read，DS 的方案要用户改代码）。证据：DS 最终说明承认"source-read 只在读顶层文档时触发"，却选择加新事件；测试输出的断言就是缺 source-read 上报。
   环境：评分跑的是 docutils 0.20.1，正常；DS 自己沙箱里是 docutils 0.17.1（低于项目要求），run2 用 shim 才能验证，属验证受阻但不是判错原因。
5. 主类别 G（偏离题面期望：自创新 API 而不是让 source-read 生效）；副 E（题目标题"source-read does not modify include'd files"明示期望，但正文未写具体接口，测试固定了 docname 和 source 内容格式）。
6. 动手前信号：有——标题直接写 source-read 应作用到 include 文件。DS 这里是自己选了设计，不是信号缺失。
7. 把握：高。

## 5. sphinx-doc__sphinx-8638
1. 题目要什么：类里 :ivar:/:var: 字段写的变量名，不应自动链接到别处同名变量（全局变量、别的类的同名变量）。
2. 标准答案：python.py 里把 'variable' 这个 PyTypedField 的 rolename='obj' 去掉（不再对变量名生成交叉引用）。
3. run1（挂）：138 轮，没动字段定义，改的是 PythonDomain.find_obj 的解析逻辑（类上下文中的非限定 attr/obj 只在本类内找）；变量名依然生成了 pending_xref（待解析引用），隐藏测试 test_info_field_list_var 要求变量名是纯 literal_strong 无引用节点，报 "node[0] is not subclass of literal_strong"（实为 pending_xref 仍在）。run2（过）：86 轮，删掉 rolename='obj'，35 项全过，与标准答案逐字相同。
4. 挂因：run1 治标（改解析规则让它解析不到）而不是治本（不生成引用）；测试检查的是 doctree 结构而非渲染结果。证据：run1 补丁在 find_obj，gold 在 PyTypedField；失败信息指向 doctree 节点类型。run2 一过，说明环境没问题（env_source=copied_from_image，Sphinx 4.1.0，docutils 0.17.1，34 项 P2P 全过）。
5. 主类别 A（题面场景窄/修法层级不同：要在源头不生成链接，run1 在下游修）；副 E（隐藏测试看节点结构）。
6. 动手前信号：弱。题面"不应链接到任何别的"，期望是"根本不链接"，可作为提示，但要看 PyTypedField 的 rolename 才知道是源头。算"弱"。
7. 把握：高。

## 6. sphinx-doc__sphinx-9229
1. 题目要什么：类型别名（如 `OtherAlias = Bar` 前面有 #: 注释或后面跟文档字符串）应显示用户写的文档，而不是默认的 "alias of ..."。
2. 标准答案：ClassDocumenter 里：doc_as_attr 时若能查到变量注释，get_doc 返回 []，add_content 也不再加 "alias of ..." 行。测试期望输出只有 `docstring`，没有 alias of 行。
3. run1（挂）：97 轮，把 ClassDocumenter.can_document_member 改成 `not isattr`，让带注释的别名走 data/attribute 文档器，并在 AttributeDocumenter 放开。run2（挂）：191 轮，重写 get_real_modname 让 ModuleAnalyzer 在别名定义的模块里找注释。两次都挂在 test_class_alias_having_doccomment，输出里 docstring 出现了，但多出一行 `   alias of :class:`target.classes.Bar``。无一过一挂。
4. 挂因：两次都把"让注释显示出来"做到了，但没做到"去掉 alias of 默认文字"；题面"instead of the alias of ... default text"其实已写明是替换。证据：两次失败信息同样是 "Left contains one more item: '   alias of :class:`target.classes.Bar`'"。环境无问题（Sphinx 4.1.0 + docutils 0.17.1，测试正常跑出 diff）。
5. 主类别 G（满足一半：注释显示但默认文字没去掉）；副 B（需要按 autodoc 现有约定：属性文档时不附加 alias 行）。
6. 动手前信号：有。题面标题"not overwriting all the default messages"和期望"instead of the ``alias of ...`` default text"明确说要替换掉。DS 没有按此核对输出。
7. 把握：高。
