## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) CarbonInterval::roundUnit (约2721行) 经 diffAsCarbonInterval 回算，丢失自定义 cascade factors（43h→1d19h），公共路径要在此处理，之后看是否需按当前因子重新归并；2) floorUnit/ceilUnit/round/floor/ceil/roundMinutes 等快捷方法都经过 roundUnit，别只改一个；3) copyProperties(2100行) 只复制部分字段，参考 cascade()/doCascade(2262行) 已有归并逻辑；4) CarbonPeriod::roundUnit(2247行) 及其 round/floor/ceil 是否走同一路径。
B. 1) 默认因子下原有取整结果不能变（如超过24h按默认归并为天）；2) 负数/invert 间隔在自定义因子下保持符号正确；3) 取整进位（59m40s→进到下一小时），floor/ceil 同样要测；4) 含 days/weeks/months 的间隔，自定义因子中有无 day 等条目。
C. 1) tests/CarbonInterval 下 roundUnit/round/floor/ceil 现有测试（如 RoundingTest）核对期望；2) setCascadeFactors 测试需重置静态因子，自测后恢复默认；3) total()(2370行) 已按自定义因子计算，取整后 hours 字段需与 totalHours 自洽；4) 文档/changelog 中 cascade 与取整的说明。
D. 1) 题面完整例子：roundMinutes 后 hours=43、totalHours=43.05；2) floorMinutes、ceilMinutes、roundSeconds 及会进位的输入；3) 恢复默认因子后结果与修复前一致，并跑现有 Rounding 测试。
