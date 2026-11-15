## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 调用点 gin.go:625 把 RedirectFixedPath 同时当作 trailingSlash 参数传入；redirectFixedPath(gin.go:680) 与 tree.go findCaseInsensitivePath/findCaseInsensitivePathRec 中 fixTrailingSlash 的所有分支都要核对；gin.go:83-99 的字段注释与行为是否一致。
B. 大小写加尾斜杠同时不匹配（如路由 /Path4/ 请求 /path4）；RedirectTrailingSlash=true 且 RedirectFixedPath=false 的原行为不变；两开关全开、非 GET(307)、rPath=="/" 与 CONNECT 的排除逻辑。
C. routes_test.go:201 TestRouteRedirectFixedPath 在 RedirectTrailingSlash=false 下断言 POST /path4 重定向到 /Path4/，依赖旧行为，很可能要同步修改；TestRouteRedirectTrailingSlash(145) 是基线；routes_test.go:471 附近的用例；tree_test.go 对 findCaseInsensitivePath 的直接调用；CHANGELOG/docs。
D. 1) 题面复现：/ping/ 得 404 且无 Location；2) 同开关下 /PING 仍重定向到 /ping，并确认 /PING/ 的结果符合预期；3) TrailingSlash=true、FixedPath=false 时 /ping/ 仍重定向，并跑完整 routes_test 和 tree_test。
