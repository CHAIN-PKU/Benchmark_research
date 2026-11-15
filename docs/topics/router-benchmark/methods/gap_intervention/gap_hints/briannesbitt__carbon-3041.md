## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但很可能也要一起处理的位置**
1. `src/Carbon/CarbonPeriod.php` 构造函数的参数循环（约第 638-642 行）。遇到 `DateTimeZone` 参数时调用 `$this->setTimezone($argument)`。`setTimezone` 开头是 `copyIfImmutable()`（约 1770 行）。对 `CarbonPeriodImmutable`，改动落在副本上，构造中的 `$this` 没有变化。请核对这是不是 Immutable 丢时区的原因，并确认 `CarbonPeriod`（可变）是否表现不同。
2. 同一个循环里字符串日期是在 `makeDateTime`（约 2455 行）里用 `$this->timezoneSetting` 解析的。时区参数排在日期之后时，解析发生在时区设置之前，日期会按默认时区（UTC）解析。请查证参数顺序的影响，并想清楚期望的语义：是把 '2024-01-01' 当作 Melbourne 本地时间，还是先解析再转换。这两种语义下 `setTimezone` 与 `shiftTimezone`（约 1770、1790 行）的区别很关键。
3. 迭代时返回日期的几个位置：`rewind()`（约 1354 行）、`prepareForReturn()`（约 2376 行）、`current()`、`toArray()`、`first()`、`last()`。`rewind()` 只在间隔带时分秒时才设置 `$this->timezone`，并转成 UTC 迭代。请确认日、周这类不带时间的间隔，以及带时间的间隔，返回的日期时区是否都正确。
4. `src/Carbon/CarbonPeriodImmutable.php` 以及 `copy()`、`toggleOptions` 一类会克隆的方法。请核对 `timezoneSetting` 和 `timezone` 属性是否被正确带到新实例。

**B. 题面没给例子、但很可能被检查的输入/边界情况**
1. 时区参数的传法不同：`DateTimeZone`、`CarbonTimeZone`、字符串、整数偏移。
2. 时区参数出现在不同位置：在日期之前、在日期之后、在间隔之后。
3. 起止日期本身是带时区的 Carbon 对象，同时又传了另一个时区参数。要想清楚以谁为准。
4. 带时分秒的间隔（如 `PT1H`、`1 hour`）、用 `recurrences` 而不是 end、以及 `last()`、`toArray()`、foreach 遍历的各个元素，是否都带正确时区。
5. `CarbonPeriod` 与 `CarbonPeriodImmutable` 两个类都要验证。

**C. 仓库里已有的约定、文档或测试中需要核对的地方**
1. 查看 `tests/CarbonPeriod/` 和 `tests/CarbonPeriodImmutable/` 下与 timezone、`setTimezone`、`shiftTimezone`、`tzName` 相关的现有测试，不要破坏它们已固定的行为。
2. `tz` / `tzname` 的 getter（约 745 行）读的是 `timezoneSetting`。修复后它应与返回日期的时区保持一致。
3. `rewind()` 注释里写了用 UTC 迭代是为了避开 DST 回拨的 bug。修改时不要破坏这条路径，并检查跨 DST 的间隔。
4. 题面提到 v2 的行为是返回指定时区，可以看看文档或升级说明里有没有相关约定。

**D. 提交前建议额外自测的情况**
1. 题面的例子，分别用 `CarbonPeriodImmutable::create(...)` 和 `CarbonPeriod::create(...)`，检查 `first()`、`last()`、`toArray()` 每个元素的 `->timezone`，以及日期的小时数是否仍是 00:00（没有被偏移）。
2. 把时区参数放到最前面，以及用字符串时区、整数偏移时区，结果是否一致。
3. 间隔改成 `PT12H` 或 `1 hour`，在含 DST 切换的时区（如 Australia/Melbourne、Europe/Paris）里遍历，检查时区和时间是否正确。
