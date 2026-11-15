## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 题面没点名、但很可能也要一起处理的位置
1. lib/helpers/isAbsoluteURL.js：正则把 //host 当成绝对地址，buildFullPath 靠它决定是否拼接 baseURL，//开头路径因此绕过 baseURL，根因大概率在这一层，不只是 http 适配器。
2. lib/adapters/http.js 第232行附近 new URL(fullPath,'http://localhost') 会给协议相对地址补协议；判断这里是否还需处理，要看上一条修完后 fullPath 的样子。
3. buildFullPath 另外两个调用点：lib/core/Axios.js 第190行（getUri）、lib/helpers/resolveConfig.js 第17行（fetch/xhr）。三处共用同一判断，改完确认行为一致。
4. dist/ 下有构建产物；先看测试引用的是 lib 还是 dist，再判断是否需要同步。

B. 题面没给例子、但很可能被检查的输入/边界情况
1. 设置了 baseURL，请求 url 为 //google.com：期望拼到 baseURL 下，而不是请求外部主机。
2. 没有 baseURL，请求 url 为 //host：是否拼接、是否报错需要考虑，别让无 baseURL 的行为被改坏。
3. 带协议地址（https://x、custom-scheme-v1.0://x、HTTP://x）仍须视为绝对地址；data: 等无 // 的 URL 保持原行为。
4. 普通相对路径（/foo、foo）、多斜杠（///x）、`/${userId}` 拼法；核对 combineURLs 对 baseURL 末尾斜杠与 url 开头斜杠的合并。

C. 仓库里已有的约定、文档或测试中，与这个行为有关、需要遵守或核对的地方
1. test/specs/helpers/isAbsoluteURL.spec.js 有一条用例断言 //example.com/ 返回 true（protocol-relative），语义改变后需与实现一并核对更新，且别带坏其他 scheme 用例。
2. test/specs/core/buildFullPath.spec.js 目前仅2条用例，没覆盖协议相对地址，可参考其写法。
3. isAbsoluteURL.js 注释写明「<scheme>:// 或 //」的定义，语义变了需同步更新注释。
4. lib/platform/common/utils.js 的 origin 默认 'http://localhost' 是 fetch 适配器单独的约定，确认是否牵涉。

D. 建议提交前额外自测的情况
1. axios.create({baseURL:'https://a.com'}).get('//evil.com') 及 getUri 的结果：最终主机必须仍是 a.com，三个适配器和 getUri 一致。
2. isAbsoluteURL 与 buildFullPath 对 https://x、HTTP://x、/foo、//x、///x 的结果，并跑现有单测看哪些断言因语义变化失败。
3. 不设 baseURL 时请求 //host 与 http://host，对比修改前后有无意外变化。
