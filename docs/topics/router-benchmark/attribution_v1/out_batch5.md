# 第5批归因（DS 失败分析）

## 1. briannesbitt__carbon-3041（PHP，CarbonPeriod 丢时区）
1. 题面：`CarbonPeriodImmutable::create('2024-01-01','2024-01-05', CarbonTimeZone::create('Australia/Melbourne'))->first()->timezone` 期望 Australia/Melbourne，实际 UTC。
2. 标准答案：构造函数里遇到时区参数时，除了 setTimezone，还把先前以字符串给出的起止日期用新时区"重新解析"（`configureTimezone`，用原始字符串重新 makeDateTime）；并新增 `makeTimezone`，让时区也能以字符串（'Australia/Melbourne'）传入；顺带让 toggleOptions 对不可变对象先 copy。
3. DS 两次几乎一样：在 `setFromAssociativeArray()` 之后再调一次 `setTimezone($this->timezoneSetting)`（把日期"转换"到新时区）。两次都自己加了测试（只断言时区名），都没过隐藏测试。run1 65 轮，run2 55 轮，都挂在同一个目标测试 `Create > Create from date strings with timezones`。（没有一过一挂。）
4. 挂因：证据——测试输出 `Expected '2024-01-01 00:00:00 Australia/Melbourne' / Actual '2024-01-01 16:00:00 Australia/Melbourne'`（tests/CarbonPeriod/CreateTest.php:504）。DS 把 UTC 零点"换算"到墨尔本，时区名对了但墙钟时间（几点几分）被改了；标准答案语义是"按该时区解释日期字符串"（保持 00:00）。另外测试还要求时区参数可以是纯字符串，DS 没做。题面只写了"timezone 应是 Melbourne"，没说墙钟时间应保持。另有一个失败 `Start and end fallback`（2024 vs 2026 的年份差）是与当前日期相关的老失败，不在目标列表，非 DS 引起。
5. 主类别 E（题面期望与测试不一致/隐藏要求：保持墙钟时间、支持字符串时区）；副类别 A（题面只写了一个场景）。
6. 动手前信号：看不出（题面只给了时区名；"换算 vs 重新解释"要看 Carbon 对其他 API 的约定才有线索，较弱）。
7. 把握：中高。

## 2. caddyserver__caddy-5404（Go，heredoc 词法分析器越界）
1. 题面：oss-fuzz 报告 `finalizeHeredoc` 里 `slice bounds out of range [4:2]`（崩溃堆栈），没写期望行为。
2. 标准答案：先 `stringVal := string(val)`，全部用字符串的字节偏移（修好 rune/字节混用）；同时**去掉 heredoc 内容末尾多出的换行**（`out = out[:len(out)-1]`），并把 `NumLineBreaks` 的 heredoc 修正由 +1 改成 +2。
3. DS 两次都只修越界：run1 先转成字符串再用字节偏移（与标准答案崩溃修复部分基本相同）；run2 改成在 rune 切片里反向找换行。两次都没去掉末尾换行，都挂在 `TestLexer`（run1 10 轮、run2 13 轮；其余测试全过）。
4. 挂因：证据——run1 输出 `Test case 26 token 1: expected text 'content' but was 'content\n'`；测试补丁把所有 heredoc 期望从 `"content\n"` 改成 `"content"`，并新增 `"extra-newline\n"`、空内容等用例。崩溃修好了，但"末尾换行不再保留"是上游同时做的行为变更，题面完全没有提及。run2 未捕获到该用例细节，但失败测试相同，推定同因。
5. 主类别 E（隐藏行为变更，题面只给崩溃堆栈）；副类别 C（崩溃修复 + 行为/行数计数需成对改）。
6. 动手前信号：看不出（仓库现有测试断言 `"content\n"`，DS 无理由改它）。
7. 把握：高（run1 有直接证据）。

## 3. django__django-11848（parse_http_date 两位年份）
1. 题面：RFC 7231，两位年份要相对当前年判断"超过50年后则算过去"，而非硬编码 70 分界。
2. 标准答案：`datetime.datetime.utcnow().year` 算当前世纪，`year - (current_year%100) > 50` 则减一个世纪。
3. run1（挂）：逻辑等价，但用了 `datetime.datetime.now(datetime.timezone.utc).year`；run2（过）：用了 `datetime.datetime.utcnow().year`。其余算法都对。
4. 挂因：证据——run1 报错 `TypeError: '>' not supported between 'MagicMock' and 'int'`，共 7 个 error。隐藏测试 `@mock.patch('django.utils.http.datetime.datetime')` 只把 `utcnow` 设了返回值，DS 调 `.now(...)` 得到 MagicMock。即逻辑对，但调用的"取当前时间"接口和测试模拟的不一致。run2 恰好用了 utcnow 所以过。
5. 主类别 E（测试 mock 了特定调用 `utcnow`）；副类别 B（仓库同期惯例是 utcnow，该文件/Django 3.1 里均如此）。F：不是——共享环境 `shared_from_django-11885` 下 run2 正常通过、其余测试都过，环境无问题。
6. 动手前信号：弱——仓库同文件/同版本代码普遍用 `utcnow`，沿用即可，但题面没说。
7. 把握：高。

## 4. django__django-12193（SplitArrayField 勾选框状态污染）
1. 题面：SplitArrayField(BooleanField) 第一个 True 之后所有勾选框都变选中；题面明确指出根因是 `CheckboxInput.get_context()` 修改了传入的 attrs 字典。
2. 标准答案：`CheckboxInput.get_context` 不再原地改 attrs，而是 `attrs = {**(attrs or {}), 'checked': True}`。
3. run1（过）：和标准答案完全一样改 `widgets.py`。run2（挂）：没动 widget，在 postgres 的 `SplitArrayWidget.get_context` 里改传 `final_attrs.copy()`。
4. 挂因：证据——run2 目标测试 `test_get_context_does_not_mutate_attrs` 失败 `AssertionError: True is not False`（直接断言 widget 不修改传入 dict）。run2 只在调用方"防御性复制"，症状修了但根因（widget 改入参）还在。postgres 测试在该环境全部 skipped，DS 自测也无法覆盖。
5. 主类别 A（修在症状处/局部调用点，正确修法在更通用的根因处）。F：否（shared_from_django-11885 环境下 run1 通过，测试跑得起来）。
6. 动手前信号：有——题面明说 CheckboxInput.get_context 修改 attrs 是根因；跟着题面走就对。
7. 把握：高。

## 5. django__django-12273（重置子模型主键不生效）
1. 题面：多表继承，把子模型实例的 pk 置 None 再 save()，应当新建而不是覆盖旧行。示例里重置的是父模型字段 `uid`。
2. 标准答案：改 `Model._set_pk_val`——设置 pk 时把所有父链接的 target 字段（如 `id`）也同步设成该值（None）。
3. run1（挂）：改 `_save_parents`，同步父 pk 时加条件 `self._state.adding`；run2（过）：同样改 `_save_parents`，且新增分支"若链接字段(ptr_id)为 None，则把父 pk 也置 None"。
4. 挂因：证据——run1 两个目标测试都 `IntegrityError: UNIQUE constraint failed: ..._profile.user_ptr_id`。测试做的是 `p2.pk=None; p2.user_ptr_id=None`（父表 id 没重置）。run1 只对"父 pk 已是 None"的情形做了修复，没处理"子链接已 None 而父 id 仍是旧值"的情形，所以父表走 UPDATE、子表 INSERT 撞唯一键。run2 补了这个分支所以过。DS 自测用的是题面示例（Restaurant/Place），与隐藏测试场景不同。
5. 主类别 A（题面只覆盖一种重置路径，通用修法要覆盖 pk 与 ptr 两种）；副类别 C（成对字段，另一半没处理）。F：否（env_source 为 null，非共享环境，两次都跑得起来）。
6. 动手前信号：弱——题面例子只重置父字段；想到"pk 属性是子表链接字段"需读 Model.pk 的实现。
7. 把握：中高。

## 6. django__django-12406（RadioSelect 外键不应有空选项）
1. 题面：ModelForm 中 FK 用 RadioSelect 且 blank=False 时，不要显示 "---------" 空选项且不要默认 checked。
2. 标准答案：`ForeignKey.formfield` 传 `blank=self.blank`；`ModelChoiceField.__init__` 新增 `blank=False` 参数，若 widget 是 RadioSelect 且 not blank 则 empty_label=None（放在 Field.__init__ 之后判断 widget）。
3. run1（挂）：也加了 `blank` 参数并传 `blank`，但判断写成 `required and (initial is not None or not blank)`，**没限定 RadioSelect**，于是所有 Select 字段 blank=False 也没了空选项。run2（挂）：只对 RadioSelect + required 去掉空选项（行为正确），但**没有 `blank` 参数**。
4. 挂因：run1 证据——p2p 大量被改坏（test_basics、test_choices_bool_empty_label、test_initial_values、test_multi_fields 等十余个），例如 `Lists differ ... != [('', '---------'), ...]`；属于 D（修好目标但改坏老测试）。run2 证据——`TypeError: __init__() got an unexpected keyword argument 'blank'`（test_choices_radio_blank 四个子用例）；测试直接以 `ModelChoiceField(..., widget=..., blank=...)` 调用，要求新增公共参数 `blank`。test_clean_model_instance 也在 run2 的失败列表，输出被截断，具体原因未核（推测同样依赖 blank 参数/新模型 `__str__`）。
5. run1 主类别 D；run2 主类别 E（隐藏 API 要求：新增 `blank` 参数，题面完全没说）。整体：E 为主，D 为 run1 的副类别。F：否。
6. 动手前信号：题面里 RadioSelect 与 blank=False 的条件已写明（run1 漏了 RadioSelect 限定，是实现疏忽）；`blank` 参数看不出。
7. 把握：高（两次都有直接证据）。

## 7. fmtlib__fmt-3863（C++，字符 range 用 {:s}/{:?s}）
1. 题面：C++23 P2286，`{:s}` 把 `vector<char>` 当字符串；表格里 `{:s}` 输出 `H	llo`（不带引号），`{:?s}` 输出 `"H\tllo"`。
2. 标准答案：`range_formatter::parse` 增加 `s`、`?s` 分支（要求 T==Char），`{:s}` 输出**带双引号**的字符串（设括号为 `"`），`?s` 走 debug 转义；并支持嵌套 `{::s}`；ranges.h 改为 include format.h。
3. DS 两次都实现了 s 与 ?s：run1（109 轮）和 run2（84 轮），`{:s}` 都输出不带引号的原字符串，都挂在 `ranges_test.format_vector`。run2 还自加了测试（也按无引号写）。
4. 挂因：证据——输出 `fmt::format("{:s}", vc)` 实际 `"abc"`（无引号），测试期望 `"\"abc\""`；`{:s}` 对 `vec` 同理；`{::s}`（嵌套）实际 `[abc, abc]`，期望 `["abc", "abc"]`。DS 严格按题面表格实现；测试（上游实际行为）要求 `{:s}` 也带引号，与题面表格矛盾。另外 `{::s}`（元素层 s）题面没提。
5. 主类别 E（题面期望与测试不一致）；副类别 B（上游 fmt 的实际约定/嵌套格式）。F：否（构建与其余 ranges 测试都通过）。
6. 动手前信号：看不出（题面明确写无引号；只有参考 P2286 的 debug/引号语义才有微弱线索）。
7. 把握：高。
