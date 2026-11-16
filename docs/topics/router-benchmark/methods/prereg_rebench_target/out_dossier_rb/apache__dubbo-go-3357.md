# 仓库档案:RemoveService / RemoveSubscribeURL

查证基于下面几处文件的阅读和 grep。没有运行测试。

## 【1 题面要点】
- 要求的行为:unregister/unsubscribe 成功后,对应的 provider/consumer URL 必须不再参与三件事:本地 metadata、服务匹配、revision 计算。
- 删一个 URL 时,其他不相关的注册要保留。
- 远端操作失败时,本地 metadata 不能被删得像成功了一样。
- 题面没有给复现和期望输出,也没有给修法建议,只给了两个接口签名:
  - `metadata.RemoveService(registryId string, url *common.URL)`
  - `metadata.RemoveSubscribeURL(registryId string, url *common.URL)`
- 两个函数都放在 `metadata/metadata.go`,无返回值。题面描述写的是"用于 unregister/unsubscribe 流程",所以调用点也要接上。

## 【2 相关代码】
- `metadata/metadata.go:40-58`:包级函数 `AddService` 和 `AddSubscribeURL` 已存在。
  - 它们操作全局 `registryMetadataInfo` map,按 registryId 懒创建 `MetadataInfo`。
  - 没有 Remove 版本,要新增。
  - 这个 map 是非并发安全的裸 map,也没有锁。
- `metadata/info/metadata_info.go:133-147`:`MetadataInfo.RemoveService` 和 `RemoveSubscribeURL` 已存在。
  - `RemoveService` 做两件事:`delete(info.Services, matchKey)`,再调 `removeUrl(exportedServiceURLs)`。
  - `removeUrl`(113-125)按 `url.ServiceKey()` 分桶,用指针相等 `u == url` 匹配。
  - 桶空了就删 key。
- `registry/servicediscovery/service_discovery_registry.go:165-170`:`UnRegister(url)` 只调 `s.UnRegisterService()`,没有碰 metadata。
- `registry/servicediscovery/service_discovery_registry.go:172-192`:`UnSubscribe` 先 `stopListen`,再 `serviceNameMapping.Remove(url)`,同样没有碰 metadata。
- `registry/servicediscovery/service_discovery_registry.go:230-240`:`Register` 里 `metadata.AddService(id, url)`,registryId 取自 `s.url.GetNonDefaultParam(constant.RegistryIdKey)`。
- `registry/servicediscovery/service_discovery_registry.go:256-258`:`Subscribe` 里 `metadata.AddSubscribeURL(id, url)`。
- `registry/servicediscovery/service_discovery_registry.go:143-163`:`UnRegisterService` 是批量注销所有实例,不看 url。
- revision 计算在 `registry/servicediscovery/customizer/service_revision_customizer.go:53-116`:
  - `Customize` 从 `GetMetadataService().GetExportedServiceURLs()` 和 `GetSubscribedURLs()` 取 URL。
  - 再用 `resolveRevision(urls)` 计算。
  - URL 为空时返回 "0",revision 为空时用 `defaultRevision`。
- `metadata/metadata_service.go:108-130`:`DefaultMetadataService` 遍历 `metadataMap`(与 `registryMetadataInfo` 是同一个 map)聚合 URL。

## 【3 并列与牵连】
- 并列对象:Service 和 Subscribe 两套,必须成对实现。
- 调用点至少两处:`UnRegister` 和 `UnSubscribe`,都在 service_discovery_registry.go。
- 其他 registry 的 `UnRegister`/`UnSubscribe`(nacos、polaris、base_registry、zk 等)没有调用 `metadata.AddService`。
  - grep 里 `metadata.AddService` 只出现在 servicediscovery 的 Register 一处。
  - 所以它们大概不用改。
- 牵连面:
  - `GetExportedServiceURLs` 和 `GetSubscribedURLs` 的结果。
  - revision customizer。
  - `GetExportedURLs` 的匹配。
  - `service_instance_host_port_customizer`(它通过 `instance.GetServiceMetadata()` 读)。
  - `protocol_ports_metadata_customizer`。
- 注册实例里的 revision 是在注册时算好的。
  - 注销后本地 revision 是否要重算,需要看 `MetadataInfo.Revision` 的维护位置。
  - 我没有找到 `.Revision =` 的计算处,只有 service_discovery_registry.go:94 在读取侧赋值。
  - 这一块需要进一步确认。

## 【4 现有测试与约定】
- `metadata/info/metadata_info_test.go:64-66`:`metadataInfo.RemoveService(url)` 之后 `assert.Empty(t, metadataInfo.Services)` 和 `assert.Empty(t, metadataInfo.GetExportedServiceURLs())`。
- `metadata/info/metadata_info_test.go:92-93`:`info.RemoveSubscribeURL(serviceUrl)` 之后 `assert.Empty(t, info.GetSubscribedURLs())`。
- `metadata/metadata_test.go:34-90`:只有 `TestAddService` 和 `TestAddSubscribeURL`,没有 Remove 测试。隐藏测试大概率会补 `TestRemoveService` 等。
- `registry/servicediscovery/service_discovery_registry_test.go`:
  - `:127-149` UnSubscribe 只断言 `mockMapping.removeCalled`。
  - UnRegister 测试(`:305-511`)都直接调 `sdReg.UnRegisterService()`,断言实例保留或移除,没涉及 metadata。
  - 测试里 Register 用了 `RegistryIdKey`(`:60-64`),Unsubscribe 的测试没有设 registryId。
- 约定:`resolveRevision` 注释写"refer to dubbo-java Metadata#calAndGetRevision",这是外部参考,但与本题无冲突。
- 与题面期望没有冲突。

## 【5 边界与隐含要求】
- registryId 不存在:`RemoveService` 不能 panic,也不能顺手创建 `MetadataInfo`(`AddService` 会懒创建,Remove 不该这样)。
- URL 不在 metadata 里:要无副作用。
- `removeUrl` 用指针相等 `u == url`。
  - unregister 传入的 URL 若是另一个等价对象,就删不掉。
  - 可能需要改成按 `String()` 或 `Equal` 比较。
  - 这是一个大概率的坑。
- `MetadataInfo.RemoveService` 按 matchKey 直接 delete `Services`。
  - 同一 `service+protocol` 如果有多个 URL(不同端口或不同 URL 对象),删一个会把仍存在的服务一并删掉。
  - 对应题面"保留不相关注册"。
  - 要判断 `exportedServiceURLs` 桶是否还有同 matchKey 的 URL 再决定是否删 `Services`。
- 失败语义:远端失败时不能删本地 metadata。
  - `UnRegister` 要在 `UnRegisterService()` 返回 nil 后才调 Remove。
  - `UnSubscribe` 要在 `serviceNameMapping.Remove` 成功后才调 Remove。
  - 注意 UnSubscribe 中途几个早退点(`!shouldSubscribe`、`services == nil`)和 Subscribe 对称性。
- `UnRegister` 当前是批量 `UnRegisterService`,不看 url。
  - 多个 URL 共用一个 app 实例,只有部分 URL 注销时怎么处理,需要决定。
- 并发:全局 map 无锁,Register/UnRegister 并发时有 data race。
- 删除后 `Revision` 字段和已计算的 revision 是否需要更新。
- 如果 `Register` 前对 URL 做过 `HandleRegisterIPAndPort`,unregister 时的 URL 可能 IP/Port 不同,影响匹配。

## 【6 改动规模】
- 必改:`metadata/metadata.go` 新增两个函数,约 15 行。
- 必改:`service_discovery_registry.go` 的 `UnRegister` 和 `UnSubscribe` 接入,约 2 处。
- 可能改:`metadata/info/metadata_info.go` 的 `removeUrl` 和 `RemoveService`,修匹配方式和保留同 matchKey 的逻辑。
- 总计 2–3 个文件、约 4–6 处,局部修补,不需要新增结构。

## 【7 难点一句话】
接口本身很简单,难点在语义细节:`removeUrl` 的指针相等匹配、`Services` 按 matchKey 整体删除、"远端失败不删本地"的接入顺序,以及 `UnRegister` 本身批量注销、不区分 URL 的现状。