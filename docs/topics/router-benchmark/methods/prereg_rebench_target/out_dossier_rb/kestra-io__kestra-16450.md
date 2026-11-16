# 仓库档案:Kestra 条件分组过滤返回 HTTP 400(TIME_RANGE)

## 【1 题面要点】
- 要求的行为:在 Executions 页面添加条件分组(默认 `OR`),再加一个过滤(如 labels `foo:bar`),后端不应再返回 400。
- 实际错误:`Invalid query filters: ... Field TIME_RANGE is not supported for resource EXECUTION. Supported fields are QUERY, SCOPE, FLOW_ID, START_DATE, END_DATE, STATE, LABELS, ...`。
- 题面没给期望输出,没给修法建议,也没给测试。Interface 一栏写的是 "No new interfaces are introduced."。
- 复现里没写请求 URL。可以推断:默认过滤集里带 `timeRange`,新建分组后 `timeRange` 被放进了 `or` 节点内。

## 【2 相关代码】
- `webserver/.../utils/QueryFilterUtils.java:117` `replaceTimeRangeWithComputedDateFilter`:Execution/Log 等接口在查询前,把 TIME_RANGE 换成 START_DATE/END_DATE。
  - `:62` `updateFilters`(START 模式)和 `:86` `updateFiltersForEndDate`(END 模式)只遍历顶层 `filters` 列表。
  - 辅助方法 `isTimeRangeFilter` 在 `:29`,`isStartDateFilter` 在 `:21`,`timeRangeOperation` 在 `:43`。
  - `:139` `rewriteTriggerDateFilters` 同样只处理顶层。
- `webserver/.../utils/TimeLineSearch.java:20` `extractFrom`:循环里 `if (filter.field()==null) continue;`,节点(`field` 为 null)被直接跳过。嵌套的 TIME_RANGE、START_DATE、END_DATE 因此取不到。
  - 它还有互斥检查(`:36`,startDate/endDate 与 timeRange 互斥)和默认 `now-8d` 的回退(`:44`)。
- `core/.../QueryFilter.java:742` `validateQueryFilters` / `:753` `collectValidationErrors`:会递归进节点,并对每个叶子校验字段。`:766-771` 产生题面里的报错信息。嵌套的 TIME_RANGE 没被替换,所以在这里被拒。
- `jdbc/.../AbstractJdbcRepository.java:245-276` `filter`:先调用 `validateQueryFilters`,再用 `andOf/orOf/toCondition` 递归生成 SQL。仓库层本来就支持树。
- `core/.../utils/DateUtils.java:120` `validateTimeline(List)`:只看顶层。
- 解析端 `webserver/.../converters/QueryFilterFormatBinder.java:25-214`:能解析 `filters[or][0][timeRange][EQUALS]` 并生成节点树。

## 【3 并列与牵连】
- 并列调用点:
  - `ExecutionController` 里有 12 处,经 `replaceTimeRangeWithComputedStartDateFilter` 调用(`:482/1060/1329/1602/1687/1700/1716/2027/2117/2213/2401`),另有 `:250` 走带 `dateFilter` 的版本。
  - `LogController:83`。
  - `TriggerController` 调 `rewriteTriggerDateFilters`(`:117/196/266/300/334/371/409/424`)。
  - `DashboardController:291/359` 直接调 `TimeLineSearch.extractFrom(filters)`。
  - 修改集中在工具类里,controller 一般不用动。
- 成对方法:`updateFilters` 和 `updateFiltersForEndDate` 要同步改。`rewriteTriggerDateFilters` 自己有一套 map,也要同步,否则 Trigger 页面有同样的 bug。
- 牵连:
  - `TimeLineSearch.extractFrom` 若改成递归,会影响 Dashboard。
  - `DateUtils.validateTimeline` 只看顶层。
- 仓库层(`AbstractJdbcTriggerRepository.java:365` 另有 ISO 时长处理)和 `Searchable.java:129`(`case OR`,内存过滤)也要和新语义保持一致。

## 【4 现有测试与约定】
- `QueryFilterUtilsTest.java:22-48` 只测顶层 TIME_RANGE,断言 `result.hasSize(1)`、field 为 START_DATE/END_DATE、op 为 `GREATER_THAN_OR_EQUAL_TO`。
- `TimeLineSearchTest.java:60-117`:`updateFilters` 对顶层 START_DATE 的行为,即既有 START_DATE 被改写成新值(`:73-87`,`hasSize(2)`)。另有 `:52` 非法时长抛 `IllegalArgumentException`。
- `QueryFilterTest.java:748` 测节点校验。`QueryFilterFormatBinderTest.java:324` 取 TIME_RANGE 叶子。
- `ExecutionControllerTest.java:452` 断言了完全相同格式的错误信息(字段为 TRIGGER_ID)。修好后,这条错误格式不能变。
- `AbstractExecutionRepositoryTest.java:396` 等仓库测试断言:直接把 TIME_RANGE 传给仓库时,应当抛"不支持"错误。所以不能靠让仓库支持 TIME_RANGE 来修。
- 约定:TIME_RANGE 只是 web 层的语法糖,在 web 层解析为日期过滤。仓库层不支持它(`AbstractJdbcRepository:547` 抛 `Unsupported field: TIME_RANGE`)。这与题面期望不冲突。
- `BlueprintController:141-151` 是反面参考:它显式拒绝逻辑分组。

## 【5 边界与隐含要求】
- 语义问题:`OR` 组里的 timeRange 该怎么处理?
  - 若原地改写成 START_DATE 并留在 OR 里,"timeRange 或 label"会变成宽松并集。
  - 也可以把它提升到顶层。这没有写明,需要自行决定,隐藏测试大概率会断言其中一种。
- 嵌套多层(`or` 里套 `and`),要递归。
- 同一棵树里有多个 TIME_RANGE。
- 节点中既有 TIME_RANGE 又有 START_DATE:`extractFrom` 的互斥检查是否要跨层生效。
- "没有日期过滤时补默认 START_DATE"(`:75`)的判断,是否要把嵌套的日期过滤也算进去。
- `NOT_EQUALS`/`NOT_IN` 时的 op 翻转(`timeRangeOperation`)在嵌套里也要保持。
- 节点和叶子的构造约束(`QueryFilter.java:35-41`):节点必须有 `logical` 且 `children` 非空。重建节点要用 builder,不能留下空 children。
- `field()==null` 的节点要避免 NPE。
- `validateTimeline` 对嵌套日期的校验。

## 【6 改动规模】
- 主要改动在 `QueryFilterUtils.java` 一个文件:3 个方法加上递归辅助方法。`TimeLineSearch.extractFrom` 可能需要小改,所以约 2 个文件、4-6 处。
- 属局部修补加递归遍历,不需要新结构,也不贯穿多层。controller 和仓库不用动。
- 隐藏测试大概在 `QueryFilterUtilsTest` / `TimeLineSearchTest`,可能还有 ExecutionController 的集成测试。

## 【7 难点一句话】
改成递归本身不难。难点在于:题面没定义"OR 分组内的 timeRange 如何落到 START_DATE"这条语义(原地改写还是提升到顶层)。隐藏测试的断言形状只能靠猜,另外几处并列实现(START、END、Trigger、`TimeLineSearch`)也容易漏改。