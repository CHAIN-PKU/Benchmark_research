## 仓库档案（CarbonPeriod 丢失时区，carbon-3041）

下面的行号都来自 `src/Carbon/CarbonPeriod.php`，没有另外标路径的都在这个文件里。我读了代码，没有运行复现。

### 【1 题面要点】
- **要求的行为**：`CarbonPeriodImmutable::create('2024-01-01','2024-01-05', CarbonTimeZone::create('Australia/Melbourne'))->first()->timezone` 应返回 `Australia/Melbourne`。题面写的实际结果是 `UTC`。
- **复现**：只有这一行代码，版本是 Carbon 3.3.1。
- **期望输出**：`Australia/Melbourne`。题面说 v2 里同样的代码是这个结果。
- **修法建议**：没有。作者只猜是不是因为改成了继承 `DatePeriod`，并说「if it is I think it might need a callout in the upgrade guide」（如果是有意为之，应该在升级指南里提一下）。
- **隐含的期望**：从期间里取出的日期（first、迭代等）应带上传入的时区。

### 【2 相关代码】
- **`__construct`（589–712）**：第 638–642 行按顺序处理参数，遇到 `DateTimeZone` 就调用 `$this->setTimezone($argument)`。
  - 这时 start/end 还没处理。`makeDateTime`（2455）读 `$this->timezoneSetting`，此时它可能还是 null 或已被设置，取决于参数顺序。
  - 起止日期是在 688 行的 `setFromAssociativeArray`（2518）里才设置的，用的是构造时的 `makeDateTime` 结果。
  - 所以字符串 `'2024-01-01'` 在时区参数排在最后时，会被解析成默认时区（UTC）。这点我没运行验证。
- **`setTimezone`（1770）**：
  - 它调用 `copyIfImmutable()`，再设置 `timezoneSetting` 和 `timezone`，并把已有的 start/end 转成该时区。
  - 在构造函数里调用它，返回值被丢弃。对 immutable 类，`copyIfImmutable`（726）会返回副本，副本上的改动因此丢失；`$this` 本身可能没有设上时区。这是我读代码推断的，没有运行验证。
  - `CarbonPeriodImmutable.php:34` 覆写了 `copyIfImmutable`，很可能是 immutable 实现。
- **`rewind`（1354–1376）**：
  - 第 1365 行 `$this->timezone = intervalHasTime(...) ? $this->carbonCurrent->getTimezone() : null;`。
  - 默认间隔是天，没有时间部分，所以 `timezone` 被置成 null，这会覆盖掉 `setTimezone` 设的值。
  - 只有间隔含时间时才转 UTC 迭代（1367–1369），用来规避 DST 回退的 bug。
- **`prepareForReturn`（2376）**：只有 `$this->timezone` 非空才对返回值 `setTimezone`。`current()`（1318）、`checkFilters`（2352）都走它。
- **`first()`（1574）**：先迭代或走 `toArray()`（1544），这两条路径最终都经过 `prepareForReturn`。
- **`getGetter`（745）的 `tzname`**：读 `timezoneSetting`，不读 `timezone`，两者语义不同。

### 【3 并列与牵连】
- 并列字段：`timezone` 是迭代用的内部时区（rewind 里会被改写），`timezoneSetting` 是用户设置，这两个字段容易混淆。
- 成对方法：`setTimezone` 与 `shiftTimezone`（1790）逻辑一致，若修改 `setTimezone` 要同步考虑后者。
- 多个入口都走 `rewind` 和 `prepareForReturn`：`first`、`last`、`toArray`、`getIterator`、`current`、`calculateEnd`（1814）、`count` 和过滤器回调。
- 改 rewind 里的 timezone 逻辑会影响所有含时间间隔的 DST 迭代。`IteratorTest.php:552` 的 `shiftTimezone('America/Toronto')` 用例直接依赖这一块。
- `CarbonPeriodImmutable` 要检查：`copyIfImmutable` 的行为是否让构造函数内的 `setTimezone` 失效。
- 通过 `DatePeriod`/`CarbonPeriod` 构造（613–629）时不会带入时区参数，不过本题不涉及。
- 题面提到的升级指南（docs）与代码修复无关，不是必改项。

### 【4 现有测试与约定】
- **`tests/CarbonPeriod/SettersTest.php:438–482`**：`testSetTimezone` 和 `testShiftTimezone`。
  - 例如 447 行 `assertSame('2018-03-25 06:00 Europe/Oslo', $period->getStartDate()->format('Y-m-d H:i e'))`。
  - 这些测试只验证 `getStartDate`、`getEndDate`、`calculateEnd` 的时区，**没有断言迭代出的元素**的时区，也没有测构造函数里传 `DateTimeZone`。
  - 两个用例的间隔是 `PT1H`，不是默认的天。
- **`IteratorTest.php:552`**：`shiftTimezone('America/Toronto')` 用例与迭代时区相关，改 rewind 后需要确认它仍通过。
- 测试里没发现构造函数传 `DateTimeZone`、且迭代结果断言时区的用例（grep 到的只有以上文件）。
- 参考实现：题面称 v2 返回 `Australia/Melbourne`，仓库里没有 v2 代码可对照。PHP `DatePeriod` 的行为也没有规范可参考。
- 与题面的冲突：我没发现现有测试断言了「默认间隔下返回 UTC」，所以改动不太会和既有测试冲突。这点只是 grep 的结论，没跑全套测试。

### 【5 边界与隐含要求】
- 时区参数的位置：在 start/end 之前、之后、之间都要生效。
- start/end 本身已带时区（`Carbon` 对象、`'… Europe/London'` 字符串）时，要不要被构造参数覆盖？对应 `setTimezone` 与 `shiftTimezone` 的语义差别，题面没说。
- 字符串日期是用给定时区解析（等同 shift），还是先按默认时区解析再转换（等同 set）。这会改变日期的实际瞬间，也影响区间边界。
- 间隔含时间和不含时间两种路径：不含时间时 `timezone` 被置 null，含时间时被设为 `carbonCurrent` 的时区。
- 可变（`CarbonPeriod`）和不可变（`CarbonPeriodImmutable`）两个类都要成立。
- 通过 `->setTimezone()` 链式调用和构造参数两种方式都应得到一致结果。
- `$period->tzName` 与迭代元素的时区保持一致。
- 用字符串或整数偏移指定时区，以及 `DateTimeZone`/`CarbonTimeZone` 对象，都要走通。
- 迭代过程中 DST 的 UTC 内部迭代不能被破坏。
- 修复后 `getStartDate()`、`calculateEnd()` 的结果不应改变。

### 【6 改动规模】
- 预计只改 `CarbonPeriod.php` 一个文件，两三处：构造函数里时区的处理顺序或写法、`rewind` 里 `timezone` 的赋值、也许 `prepareForReturn`。
- 属于局部修补，不需要新增结构或跨层改动。
- 需要补测试：在 `tests/CarbonPeriod` 下加构造传时区、断言迭代元素和 `first()` 时区的用例，可变、不可变各一个。

### 【7 难点一句话】
难在弄清是哪一环让时区丢失（构造函数里 `setTimezone` 的返回值被丢弃、参数顺序、还是 `rewind` 把 `timezone` 置 null），并在不破坏含时间间隔的 UTC 迭代与 DST 行为的前提下，只让返回的日期带上用户指定的时区。