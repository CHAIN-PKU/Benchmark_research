**档案：http_server helper 的 FrozenError**

**【1 题面要点】**
- 期望行为：在使用 http_server helper 的 input 插件里加 `# frozen_string_literal: true` 后，路由注册不应报错。题面写的是 "Works well"。
- 复现：只有一句 "Add magic comment of `# frozen_string_literal: true` into input plugin using http_server plugin helper"，没有可运行的最小用例。
- 堆栈：`FrozenError: can't modify frozen String: "/example/hello"`，位置 `http_server/server.rb:84 in '<<'`。堆栈里的行号是 84，快照里 `path << '/'` 在第 81 行，所以报告的是别的版本，不影响定位。
- 题面没有给修法建议。
- 触发路径：`test/plugin_helper/test_http_server_helper.rb:375` 调用 `s.get('/example/hello')`，经 `http_server.rb:70` 的 `http_server_create_http_server` 块。

**【2 相关代码】**
- `lib/fluent/plugin_helper/http_server/server.rb:78-90`：对 `Methods::ALL` 的每个方法 `define_method(name) do |path, app=nil, &block|`。
  - 第 80-82 行：`unless path.end_with?('/') ; path << '/'`。这是原地修改调用方传入的字符串，是根因。
  - 第 84 行：校验 `(block && app) || (!block && !app)`，不合法就 `raise`。
  - 第 88 行：`@router.mount(name, path, app || block)`。
- `lib/fluent/plugin_helper/http_server/router.rb:37-43`：`mount` 把 path 作为 hash key，重复挂载就 `raise "#{path} is already mounted"`。`route!` 第 48-50 行用 `fetch(path, @default_app)` 查找。

**【3 并列与牵连】**
- 并列实现：`http_server/compat/server.rb:69-78`（webrick 兼容服务器）。
  - 它没有 `path << '/'`，只做 `@methods << [path, name, app||block]`，所以不会报 FrozenError。
  - `build_handler`（第 83-86 行）用 `group_by(&:first)` 按 path 分组后 `@server.mount(path, klass)`。
  - 这里不做末尾 `/` 的规范化。查询时 webrick 与 async 版本的 path 匹配是否一致，我没有确认。
- 调用点：
  - `in_monitor_agent.rb:214-217`，路径是 `/api/plugins` 等字面量。该文件是否有 frozen_string_literal 魔法注释，我没查。
  - `in_http.rb` 不走这个 helper，它用自己的 `on_request`。
  - `test_http_server_helper.rb` 里有大量 `s.get('/example/hello')` 调用。
- 修复会影响所有通过 async 版本 Server 注册路由的插件。调用方传入的字符串不再被改动，路由匹配行为应保持不变。

**【4 现有测试与约定】**
- `test_http_server_helper.rb:158-165`：同一路径 `/example/hello` 注册 6 种方法，请求时按该路径匹配。
- `:185`：`s.get('example/hello')`，没有前导 `/`。
- `:186`：`s.get('/example/hello2/')`，已有末尾 `/`。这两条用来验证规范化。我没读断言本身，看不到具体断言了什么。
- `:200`：`s.get(...) { raise 'error!' }`，测试错误处理。
- 测试文件自身是否带 `frozen_string_literal`，我没确认。隐藏测试很可能是加上该魔法注释，或传入 `.freeze` 的路径。
- 约定：Ruby 的 frozen string literal 语义规定不能修改字面量。题面期望与现有测试不冲突，现有测试没有断言“调用方字符串被改动”。

**【5 边界与隐含要求】**
- 传入已冻结的字符串，无论是否以 `/` 结尾，都不能报错。
- 传入不冻结的字符串时，调用方的原对象最好不被改动（改用非破坏性写法）。
- 保留规范化行为：`'example/hello'` 和 `'/example/hello2/'` 的现有测试要继续通过。
- 重复挂载的检测仍以规范化后的 path 为 key。
- compat 版本（webrick）不改动字符串，不需要同步修。
- 同一仓库里 `lib/` 其他地方是否也有原地改动 path 的写法，我只 grep 了 http_server 相关目录，没有全仓检查。

**【6 改动规模】**
- 1 个文件、1 处：`server.rb` 第 81 行，把原地追加改成非破坏性写法，例如 `path += '/'` 或 `path = "#{path}/"`。
- 可能顺带加 1 个测试，覆盖冻结字符串。这是局部修补，不新增结构，也不跨层。

**【7 难点一句话】**
- 定位很容易，堆栈已直接指到出错行。难点只在于别漏掉隐藏测试可能检查的细节：不改动调用方字符串，以及不破坏路径规范化与重复挂载检测。