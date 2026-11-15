# DS 挂题深度归因 v2（三层，2026-11-15）

范围：46 道挂题（训练 28 + 干净留出 18），剔除疑似环境 4 道（preact-3345、preact-4436、valkey-928、caddy-5404）后 **42 道有效**。Sonnet 逐题写，Opus 审（抽查证据与标准答案、补丁一致）。格式见 deep_schema.md，原始记录 deep_attribution_46.jsonl。

## 一、汇总

**L2 DS 为什么没做对（过程层，看 DS 的完整操作记录）**

- 照题面字面做，没质疑：14 道（33%）
- 跑了测试，但自己写的测试没覆盖关键情况：13 道（31%）
- 定位错根因（修症状处）：6 道（14%）
- 没去找并列实现/调用点：4 道（10%）
- 其他：3 道（7%）
- 误解现有行为：1 道（2%）
- 过早收工：1 道（2%）

**L3 动手前能不能看出来**

- repo：26 道（62%）
- issue：13 道（31%）
- none：3 道（7%）

**L1 粗类**：WRONG_LOC 9、NARROW 9、SIBLING 8、HIDDEN 6、OTHER 6、OVERGEN 4

读法：DS 几乎都跑了测试，但测试是它自己写的、只测题面那一种情况；最常见的两种过程失误是「照题面字面做」和「自测太窄」。93% 的挂题动手前在题面或仓库里有可见线索——每道都给出了一个具体的事前问题（下表最后一列），这些问题就是清单 v2 的素材。

## 二、20 道样例

| 题 | 具体特征 | DS 过程失误 | 线索在哪 | 事前该问的一个问题 |
|---|---|---|---|---|
| mrdoob__three.js-26589 | 并列copy方法漏改 | 其他 | repo | 带material数组的对象类型有哪几个？它们的copy()是否都要改？ |
| google__gson-1100 | 读写对称 null 漏改反向 | 没去找并列实现/调用点 | repo | write 修了 null，read 对 JSON null 会怎样？ |
| gin-gonic__gin-1957 | Bind与ShouldBind并列漏一 | 没去找并列实现/调用点 | repo | 新增 binding 时仓库其它 binding 暴露了哪几个 Context 方法？ |
| phpoffice__phpspreadsheet-4313 | 同类并列转换函数漏改 | 没去找并列实现/调用点 | repo | 同一正则缺陷在该文件其他函数里是否也存在？ |
| php-cs-fixer__php-cs-fixer-7663 | 无花括号 do-while 体缩进 | 没去找并列实现/调用点 | repo | PHP 中还有哪些控制结构可省略花括号？ |
| google__gson-2061 | 并列 Reader 子类 hasNext 漏改 | 过早收工 | repo | JsonReader 有哪些子类也重写了 hasNext？ |
| axios__axios-6539 | 协议相对URL应拼baseURL | 照题面字面做，没质疑 | issue | 题面有几种可接受期望？哪一种让 buildFullPath 仍拼接 baseURL？ |
| caddyserver__caddy-6115 | Secure 属性缺少 TLS 条件 | 照题面字面做，没质疑 | issue | 明文 HTTP 请求下发 Secure cookie 会怎样？ |
| caddyserver__caddy-6051 | 空白行判空过宽 | 照题面字面做，没质疑 | issue | 含空白的‘空行’要保留原样、还是视同空行？ |
| django__django-12193 | 改调用方不改被改函数 | 照题面字面做，没质疑 | issue | 根因点名的函数本身是否应改，还是只防住这一个调用方？ |
| laravel__framework-46234 | URL 尾斜杠规范化 | 跑了测试，但自己写的测试没覆盖关键情况 | repo | referer 为根路径时 to() 与 fullUrl() 字符串是否一致？ |
| sharkdp__bat-2835 | 面板宽度为0时缩进多算 | 跑了测试，但自己写的测试没覆盖关键情况 | repo | panel_width 为 0 时 grid 缩进还算 2 列吗？ |
| uutils__coreutils-6377 | 忽略信号设置在子进程而非自身 | 跑了测试，但自己写的测试没覆盖关键情况 | repo | env 是 exec 还是 spawn 子进程？信号该在哪个进程上忽略？ |
| projectlombok__lombok-3371 | TYPE_USE 层级判定过宽 | 跑了测试，但自己写的测试没覆盖关键情况 | repo | int[] @NonNull [] 的注解到底属于字段还是元素类型？ |
| jekyll__jekyll-9141 | 症状处修补非源头去重 | 定位错根因（修症状处） | repo | 同一文件为何出现两次——是谁在重复产出它？ |
| sphinx-doc__sphinx-8638 | 改解析端而非字段定义 | 定位错根因（修症状处） | repo | 是谁给 :ivar: 字段名生成了链接——字段定义还是解析器？ |
| fmtlib__fmt-3863 | 字符范围 :s 输出加引号 | 照题面字面做，没质疑 | issue | P2286 的 {:s} 对字符范围是否带引号，与 string 的 :s 一样吗？ |
| rubocop__rubocop-13396 | send 与 csend 并列分支漏改 | 跑了测试，但自己写的测试没覆盖关键情况 | repo | 这个判断对 &. 调用（csend）是否也成立？ |
| phpoffice__phpspreadsheet-3570 | 数组索引应逐元素展开 | 照题面字面做，没质疑 | repo | lookup_value 为数组时已有展开，index 数组为何不同？ |
| laravel__framework-48573 | TTL到点边界含等号 | 照题面字面做，没质疑 | none | 恰好到 TTL 秒时该键应算过期还是仍有效？ |

## 三、局限
- L2 依据的是压缩后的操作摘要（每步工具名+参数前 160 字），caddy-6051 摘要为空，L2 标未知。
- 3 道 confidence=low；21 道 med，主要是测试输出被截断、只能由补丁推断机制。
- 一过一挂的题只归因挂的那次；两次挂法不同的（django-12406）只取一个主标签。
