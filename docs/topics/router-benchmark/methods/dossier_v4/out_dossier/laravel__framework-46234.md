**档案：URL::previous() 在上一个 URL 与当前 URL 相同时不使用 fallback**

**【1 题面要点】**
- 要求的行为：调用 `URL::previous('/with-a-fallback')` 时，如果 referrer 与当前请求 URL 相同，应该使用 fallback。
- 复现：路由 `Route::get('previous-test', fn () => URL::previous('/with-a-fallback'));`，在浏览器里打开 `/previous-test`。
- 期望输出：`http://localhost/with-a-fallback`。实际输出：`http://localhost/previous-test`。
- 题面原话："there is no check for that case though."
- 题面没有给修法建议。没有说比较哪个 URL（`full()` 还是 `current()`），也没有说 `previous()` 不带 fallback 时怎么办。

**【2 相关代码】**
- `src/Illuminate/Routing/UrlGenerator.php:155-168`，`previous($fallback = false)`：
  - 先取 `referer` 头，有就返回 `$this->to($referrer)`，没有就从 session 取 `getPreviousUrlFromSession()`。
  - 取到 `$url` 就直接返回。没取到则有 fallback 返回 `to($fallback)`，否则返回 `to('/')`。
  - 全程没有和当前 URL 做比较，这是要改的核心位置。
- `UrlGenerator.php:188-193`，`getPreviousUrlFromSession()`：返回 `session->previousUrl()`。
- `UrlGenerator.php:134` `full()` 返回 `request->fullUrl()`，`:144` `current()` 返回 `to(getPathInfo())`。这两个方法可用于比较，区别在是否带 query string。
- `src/Illuminate/Session/Store.php:702-716`，`previousUrl()` 和 `setPreviousUrl()`，键为 `_previous.url`。
- `src/Illuminate/Session/Middleware/StartSession.php:200-209`，`storeCurrentUrl()` 在每个 GET 请求结束时保存 `$request->fullUrl()`。
  - 刷新页面时 referer 通常是同一个 URL。
  - 如果没有 referer，session 里的 previous 就是上一次的当前页。

**【3 并列与牵连】**
- 并列实现：referer 和 session 两条分支都要处理。fallback 判断应放在取到 `$url` 之后，不能只改其中一支。
- 成对方法：`previousPath()`（`UrlGenerator.php:176-181`）直接调用 `previous($fallback)`，会自动受益，不需要单独改。
- 调用点：
  - `Redirector::back()`（`Redirector.php:46-49`）会受影响。
  - `Redirector::guest()`（`Redirector.php:78`）在非 GET 请求时调用 `previous()`。
  - `Foundation/Http/FormRequest.php:170` 的 `getRedirectUrl`。
  - `Foundation/Exceptions/Handler.php:521` 的 `url()->previous()`。
- 对这些调用点的影响：
  - 未传 fallback 时，如果改成"相同就走 `to('/')`"，会改变现有行为，例如校验失败后重定向回自身。
  - 重定向回当前页本来是合法的行为，比如表单页 GET 之后 POST 失败回到该页。
  - 此时 referer 是表单页，当前 URL 是 POST 地址。若表单 action 与页面同 URL，两者相同，重定向行为就会变化。
- 契约和门面：`Contracts/Routing/UrlGenerator.php:20` 和 `Support/Facades/URL.php:8-9` 的签名不用动。

**【4 现有测试与约定】**
- `tests/Routing/RoutingUrlGeneratorTest.php:699-713`，`testPrevious`：
  - 当前请求为 `http://www.foo.com/`，referer 为 `http://www.bar.com/`，断言 `assertSame('http://www.bar.com/', $url->previous())`。
  - 移除 referer 后断言 `assertEquals($url->to('/'), $url->previous())`。
  - 然后断言 `assertEquals($url->to('/foo'), $url->previous('/foo'))`。
- `testPreviousPath`（`:715-735`）：
  - 当前请求是 `http://www.foo.com/`，referer 设为 `http://www.foo.com?baz=bah`，断言 `assertSame('/', $url->previousPath())`。
  - referer 为 `http://www.foo.com/bar?baz=bah` 时断言 `'/bar'`。
- 这些测试的 referer 要么和当前 URL 不同，要么 fallback 与结果一致，所以多数不会因新增的比较而失败。
- 需留意 `previousPath` 的第一组断言：referer 是 `http://www.foo.com?baz=bah`，当前是 `http://www.foo.com/`。
  - 若比较用 `full()`，两者不同，不会命中。
  - 若比较用 `current()`，规范化后可能相同，此时没有 fallback 会返回 `to('/')`，结果仍是 `/`。
- `tests/Routing/RoutingRedirectorTest.php:126-132`：`back()` 测试里 `url->previous` 是 mock，不受影响。
- 仓库没有给出规范，也没有参考实现，隐藏测试很可能加在 `testPrevious` 里。
- 题面期望与现有断言没有冲突。

**【5 边界与隐含要求】**
- 比较对象：referer 是否和 `$this->request->fullUrl()` 比较（带 query）还是和 `current()` 比较，题面没说。
- referer 经过 `to()` 规范化。比较时要用同一形式，比如是否补全 scheme 和 host。
- 没有传 fallback（`false`）时，应保持返回原 URL，不要变成 `to('/')`，否则会破坏表单重定向回自身。
- session 分支同样要判断，因为 `storeCurrentUrl` 存的就是 `fullUrl()`。
- fallback 本身可能是路径、数组或 route URL，要沿用现有 `to($fallback)` 的处理方式。
- 域名大小写、尾部斜杠、query 顺序这类规范化，题面没要求，大概率不用处理。

**【6 改动规模】**
- 改 1 个文件、1 个方法（`UrlGenerator::previous`），大约 3 到 6 行。
- 不需要新增结构，也不贯穿多层，是局部修补。
- 测试补在 `RoutingUrlGeneratorTest::testPrevious` 里。

**【7 难点一句话】**
代码本身很简单，难点是决定比较哪个 URL（`full()` 还是 `current()`），以及没传 fallback 时不能改变现有行为，这些题面都没明说，要靠推断才能和隐藏测试对上。