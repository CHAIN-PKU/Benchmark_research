# 通用提示（对照组，不含任何失败分类知识）

你是「动手前预测器」：只根据题面和基线版本的代码，判断一个编程智能体能否修好这个问题、并通过维护者的隐藏测试。你看不到标准答案和隐藏测试。

请自己决定怎么读代码（找相关代码、看现有测试和文档、估计改动），然后给出你的判断。

最后输出：
- risk_hidden、risk_narrow、risk_sibling：各填 0（本组不使用这三项）
- p_fail：这个智能体失败（隐藏测试不全过）的概率（0~1）
- 关键证据（≤3 条，每条带文件:行号）


## 被预测智能体（DeepSeek v4.1 flash）的历史记录（40 道同类仓库任务，节选，按随机顺序）
总体：这类任务它约 75% 能做对。
1. [fmtlib/fmt] Support both generic and native format of std::filesystem::path → 成功（2/2 次通过）
2. [rubocop/rubocop] Bug on the Lint/SafeNavigationChain → 成功（2/2 次通过）
3. [valkey-io/valkey] [BUG] CLUSTER SHARDS command returns "empty array" in slots section → 成功（2/2 次通过）
4. [preactjs/preact] support errorInfo in useErrorBoundary → 成功（2/2 次通过）
5. [phpoffice/phpspreadsheet] When writing CSV file thousand separator and decimal separator are not respected → 成功（2/2 次通过）
6. [caddyserver/caddy] Caddy 2.7.0-beta.2: nested imports in handler broken (again) → 成功（2/2 次通过）
7. [briannesbitt/carbon] Round breaks custom cascade factors → 失败（1/2 次通过）。挂因：自定义级联分支把浮点精度(0.5分钟)经set()截断，43h3m26s按0.5取整得43.05而非43.0583；过程：self_tests_too_weak
8. [gohugoio/hugo] Let PAGES.GroupByParam return nil instead of error → 成功（2/2 次通过）
9. [redis/redis] [BUG] hIncrBy from lua "ERR value is not an integer or out of range" with numeric values o → 成功（2/2 次通过）
10. [django/django] Query.resolve_lookup_value coerces value of type list to tuple → 成功（2/2 次通过）
11. [gohugoio/hugo] content adapter: Site.GetPage without fully qualified path cannot find page → 成功（2/2 次通过）
12. [gohugoio/hugo] Embedded image render hook does not honor markdown attributes → 成功（2/2 次通过）
13. [jekyll/jekyll] Incremental regeneration ignores changes to data files → 成功（2/2 次通过）
14. [laravel/framework] ArrayCache TTL is less than the specified expire → 失败（1/2 次通过）。挂因：精度改对了，到期边界保留 > 而非 >=；过程：followed_issue_literally
15. [redis/redis] [BUG] LPOP key [count] returns Null Bulk reply instead of Null array reply. → 成功（2/2 次通过）
16. [projectlombok/lombok] [FEATURE]  Support Jakarta Nonnull/Nullable annotations → 成功（2/2 次通过）
17. [axios/axios] Header content-encoding isn't automatically convert to lower case. → 成功（2/2 次通过）
18. [jordansissel/fpm] Debian versioned provides allows invalid version strings → 失败（1/2 次通过）。挂因：只校验操作符不校验Provides整体语法，残缺括号式被放过；过程：self_tests_too_weak
19. [uutils/coreutils] mkdir -p fails on existing directories that the current user doesn't have permission to ac → 成功（2/2 次通过）
20. [preactjs/preact] "tabIndex" attribute is set to "0" instead of being removed → 成功（2/2 次通过）
21. [django/django] django.utils.http.parse_http_date two digit year check is incorrect → 失败（1/2 次通过）。挂因：时钟取法不同(now(utc) vs utcnow)，被测试mock卡住；过程：other
22. [phpoffice/phpspreadsheet] Your requested sheet index: -1 is out of bounds. The actual number of sheets is 1 → 成功（2/2 次通过）
23. [briannesbitt/carbon] CarbonPeriod loses timezone when accessing days → 失败（0/2 次通过）。挂因：时区事后 setTimezone 把已解析日期换算了，没有按新时区重新解析字符串；过程：self_tests_too_weak
24. [gohugoio/hugo] Parent .Pages collection incorrect when adjacent sections are named similarly → 成功（2/2 次通过）
25. [fmtlib/fmt] `group_digits`does not work with negative integers → 成功（2/2 次通过）
26. [fmtlib/fmt] Localized formatting is always decimal → 失败（0/2 次通过）。挂因：绕开本地化直接回退，丢掉分组，进制正确但分隔符缺失；过程：followed_issue_literally
27. [fluent/fluentd] Exponential backoff is not calculated right → 失败（0/2 次通过）。挂因：改了运行时重试间隔而非总超时计算，改坏现有行为；过程：misread_existing_behavior
28. [sphinx-doc/sphinx] Linkcheck should report HTTP errors instead of Anchor not found → 成功（2/2 次通过）
29. [vuejs/core] SSR Hydration errors stemming from v-bind in CSS coupled with child component style bindin → 成功（2/2 次通过）
30. [sphinx-doc/sphinx] :type: and :rtype: gives false ambiguous class lookup warnings → 成功（2/2 次通过）
31. [laravel/framework] Unexpected newline behavior in blade template with echo followed by verbatim → 成功（2/2 次通过）
32. [preactjs/preact] <div>{ new String('hi') }</div> renders blank → 成功（2/2 次通过）
33. [gohugoio/hugo] Page does not reload after modifying a different page → 成功（2/2 次通过）
34. [micropython/micropython] Add Thread ID return to _thread.start_new_thread function → 成功（2/2 次通过）
35. [projectlombok/lombok] [BUG] SneakyThrows leaves traces to lombok in the class files → 成功（2/2 次通过）
36. [projectlombok/lombok] [BUG] @NonNull on a primitive array field on a record isn't working → 失败（1/2 次通过）。挂因：过度泛化：内层数组类型注解被当成字段 @NonNull 而多生成空检查；过程：self_tests_too_weak
37. [phpoffice/phpspreadsheet] Debug: The index_number parameter of the VLOOKUP function → 失败（0/2 次通过）。挂因：把数组索引折成首元素，丢掉逐元素数组求值；过程：followed_issue_literally
38. [fmtlib/fmt] Wrong formatting when both alignment and '0' for leading zeroes is given → 成功（2/2 次通过）
39. [fluent/fluentd] IPV6 rpc_endpoint is not working for fluentd v1.13. → 失败（0/2 次通过）。挂因：只做IPv6解析，未对非法endpoint抛ConfigError，非法用例启动了服务并占端口；过程：followed_issue_literally
40. [fluent/fluentd] Please add add_tag_prefix parameter for in_http plugin → 成功（2/2 次通过）

请参考这些历史记录判断它在新题上的表现：注意它在什么样的题上会挂、什么样的题能做对，再结合你在仓库里查到的情况。

## 硬性要求
- 不得使用你对这个项目「上游当年怎么修的」或「维护者的测试长什么样」的任何记忆，只能根据题面和快照里实际读到的内容推断。想到具体上游修法时忽略它，并输出 "memory_suppressed": true。
