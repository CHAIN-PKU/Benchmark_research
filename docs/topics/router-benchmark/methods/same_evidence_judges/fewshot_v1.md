## 判断示范（来自另一位判断准确的审查者；请学习它如何按本题具体情况给风险和利好定分量）

### 示范：Debian versioned provides allows invalid version strings
证据：lib/fpm/package/deb.rb:777-797 fix_provides has no validation of version operators；题面原文: dpkg only allows exact version Provides with `=`. If fpm checked for that, I would have caught the error at build time；lib/fpm/package/deb.rb:429 and :659 fix_provides called in two places; spec/fpm/package/deb_spec.rb:146-240 only tests names
一位判断准确的审查者列出的因素：
  - 更难（大）：题面未规定具体行为
  - 更难（大）：隐藏测试可能依赖具体异常或消息
  - 更容易（中）：改动集中在 fix_provides 一处
  - 更容易（小）：有两个调用点，需都覆盖
  - 更难（中）：需处理多种运算符与边界格式
它给的失败概率：0.55；真实结果：失败

### 示范：`env`: implement `--ignore-signal`
证据：src/uu/env/src/env.rs:116-200 (uu_app has no ignore-signal arg; the existing args are chdir, argv0 and so on)；src/uucore/src/lib/features/signals.rs:342 (signal_by_name_or_value accepts names, numbers and SIG-prefixed names; the ALL_SIGNALS index is not an OS signal number on every platform)；题面原文: `--ignore-signal[=SIG]  set handling of SIG signal(s) to do nothing` (optional value, so an empty list means all signals; GNU also accepts a comma-separated list and rejects an invalid signal name with
一位判断准确的审查者列出的因素：
  - 更难（中）：可选值且空值表示全部信号
  - 更难（中）：逗号分隔列表与无效信号的报错文本
  - 更难（中）：需用 libc 把信号设为 SIG_IGN 并在 exec 后保持
  - 更容易（中）：信号名解析已有现成函数可复用
  - 更难（小）：ALL_SIGNALS 索引不等于 OS 信号号，易踩坑
  - 更难（中）：隐藏测试可能覆盖 SIGKILL/SIGSTOP 等边界和 -v 输出
它给的失败概率：0.5；真实结果：失败

### 示范：support bind http header param
证据：binding/query.go:14-20 (queryBinding is the template; a headerBinding needs Name() returning a fixed string, and the hidden test likely checks it)；binding/form_mapping.go:138-141 (setByForm looks up form[tagValue] directly; header keys are canonicalized, so a tag like `header:"rate"` would not match without extra handling)；context.go:630-633 (ShouldBindQuery has a sibling MustBind variant BindQuery at context.go:577; the issue only asks for ShouldBindHeader, so BindHeader and binding.Header may 
一位判断准确的审查者列出的因素：
  - 更难（中）：需新增 binding.Header 与 Name 字符串
  - 更难（大）：header 键规范化与 tag 大小写匹配
  - 更难（中）：可能遗漏 BindHeader 和 binding.Header 导出变量
  - 更容易（中）：有 queryBinding 现成模板可照抄
  - 更难（中）：题面只给 ShouldBindHeader 示例，隐藏测试细节不明
它给的失败概率：0.45；真实结果：失败

### 示范：Class Sphere is missing property isSphere
证据：src/math/Sphere.js:10-15 constructor lacks this.isSphere = true；src/math/Box3.js:7 this.isBox3 = true; src/math/Plane.js:12 this.isPlane = true；test/unit/src/math/Plane.tests.js:54-60 isPlane test pattern (true on instance, falsy on plain object)
一位判断准确的审查者列出的因素：
  - 更容易（大）：只需在构造函数加一行属性
  - 更容易（大）：仓库内已有同类写法可照抄
  - 更容易（中）：隐藏测试模式明确，与现有 isPlane 测试一致
  - 更容易（中）：题面明确指出属性名，无歧义
它给的失败概率：0.03；真实结果：成功

### 示范：Incorrect translation of xlink:href attribute -> hhref
证据：src/diff/props.js:109: name = name.replace(/xlink[H:h]/, 'h').replace(/sName$/, 's');；src/diff/props.js:107: comment says xlink:href / xlinkHref --> href；test/browser/svg.test.js:48: the existing test covers only xlinkHref, so xlink:href has no test
一位判断准确的审查者列出的因素：
  - 更容易（大）：单行正则修复，定位明确
  - 更容易（中）：题面直接给出修法建议
  - 更容易（小）：隐藏测试可能覆盖 xlink:href 与 xlinkHref 两种写法
  - 更难（小）：需注意 sName 替换与其他属性不被误伤
它给的失败概率：0.07；真实结果：成功

### 示范：PromQL function day_of_year
证据：promql/functions.go:1034 (funcDayOfWeek is the template; the new function also needs entries in the FunctionCalls map at :1091 and in AtModifierUnsafeFunctions at :1146)；promql/parser/functions.go:129 (day_of_week definition; day_of_year needs a parallel entry)；docs/querying/functions.md:100 (docs section to mirror), plus UI files web/ui/module/codemirror-promql/src/types/function.ts:221 and promql.terms.ts:175
一位判断准确的审查者列出的因素：
  - 更容易（大）：有现成模板 day_of_week
  - 更难（中）：需改多处注册点
  - 更难（小）：隐藏测试可能含 testdata 与 parser 测试
  - 更容易（中）：语义简单：YearDay 即可
  - 更容易（小）：文档和UI非测试必需
它给的失败概率：0.07；真实结果：成功
