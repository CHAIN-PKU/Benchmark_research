## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 同类位置
1. UrlGenerator::previous() 是唯一判断点；referer 分支与 getPreviousUrlFromSession() 分支并列，检查「与当前相同」时需考虑两条来源是否都覆盖。
2. previousPath()、Redirector::back()（传 fallback）、Redirector::guest()（无参 previous()）都会继承新行为，需核对。
3. FormRequest::getRedirectUrl（Foundation/Http/FormRequest.php:170）与 Exceptions/Handler.php:521 调用 previous()，验证失败重定向可能指回当前页。

B. 边界输入
1. 比较基准：current() 不含 query，full() 含 query；referer 带 query 时算不算相同要想清楚。
2. 末尾斜杠、根路径 /，以及 referer 经 to() 规范化后的比较一致性。
3. 无 fallback(false) 且 previous 等于 current 时的行为需有意识决定。
4. fallback 为 route() 生成的完整 URL 或相对路径都应正常。

C. 已有约定/测试
1. tests/Routing/RoutingUrlGeneratorTest.php 的 testPrevious / testPreviousPath 以根路径请求，且 testPreviousPath 的 referer 与当前页同路径（http://www.foo.com?baz=bah），期望返回 '/'，不能被新逻辑破坏。
2. Contracts/Routing/UrlGenerator.php 与 Facades/URL.php 的 previous 注释，语义变化时可能需同步。
3. tests/Routing/RoutingRedirectorTest.php 的 back() 测试要确认不受影响。

D. 提交前自测
1. 请求 /previous-test、referer 同为该 URL、传 fallback，应得到 fallback。
2. referer 为不同页面时仍返回 referer；无 referer 时走原 session/fallback 逻辑。
3. referer 与当前相同且无 fallback；并跑现有 testPrevious、testPreviousPath。
