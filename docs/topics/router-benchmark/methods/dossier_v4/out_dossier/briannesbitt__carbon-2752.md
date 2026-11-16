**档案：`Carbon::is('January')` 对 10 月 1 日返回 true（Carbon 2.65.0）**

我没有运行代码。Bash 的 PHP 探测命令被权限拦截了。下面关于 `modify` 行为的说明，是我读代码推出来的，没有实测。

**【1 题面要点】**
- 要求的行为：`Carbon::create(2023,10,01)->is('January')` 应返回 `false`，实际返回 `true`。
- 复现：`$today = Carbon::create(2023, 10, 01); $today->is('January'); // true`。
- 期望输出：`I expected to get: false`。
- 题面没有给修法建议，也没有说明触发条件。条件要自己推断，很可能是“日期的日为 1，且月份名与当前月份不同”。
- 题面只给了 `January` 一个例子，没有其他月份或日期。

**【2 相关代码】**
- 主要文件是 `src/Carbon/Traits/Comparison.php`，里面的 `is(string $tester)` 在第 989–1054 行。
- 第 1005–1011 行：
  - `$median = static::parse('5555-06-15 12:30:30.555555')->modify($modifier)`。
  - `$current = $this->avoidMutation()`。
  - `$other = $this->avoidMutation()->modify($modifier)`。
  - `$other` 就是把 `$tester` 当作 PHP `modify()` 修饰串去修改当前日期。
- 第 1013 行：`current` 等于 `other` 时直接返回 true。
- 第 1017–1034 行：按正则分别处理秒、分、小时、“月名 + 数字”。
- 第 1036–1051 行：`$units` 表里，`month => [1,'year']` 排在最前。逻辑是：如果 `median` 经修饰后 `month` 等于 1，就把 `$current` 截断到年初。
- 第 1053 行：`return $current->eq($other)`。
- 推测的根因，针对 `'January'`：
  - `median` 是 6 月 15 日，被改成 `January` 后月份为 1。
  - 这与 `$minimum=1` 相等，所以 `current` 被 `startOfYear` 成 2023-01-01。
  - `other` 是 2023-10-01 经 `modify('January')` 的结果。月份名通常只改月份，日保持为 1，所以我推断是 2023-01-01。
  - 两者相等，返回 true。
- 这段逻辑的原意是“修饰串改了月份，就按年粒度比较”，意图本来是判断“是否同一个月”。
- 但它把 `current` 截断到年初，而不是月初，所以只要日恰好为 1，就会误判。
- 日不是 1 时，`other` 的日会保留成别的值，所以不相等，bug 不出现。
- 按这个思路，`current` 应该用 `startOfMonth`，或者直接比较月份。
- 其他单位同理：`day => [1,'month']` 对应月，`hour => [0,'day']` 对应日。月份这条是“minimum=1”碰巧与“1 月”重合。
- 这是我的推断，没有实测。

**【3 并列与牵连】**
- 并列声明：`src/Carbon/CarbonInterface.php:2570-2582` 只有 docblock 示例，没有逻辑。
- 逻辑只在 `Comparison.php` 这一处。`Carbon`、`CarbonImmutable`、`CarbonInterface` 都通过 trait 共用。
- 相关的 `isSameMonth`（约第 741 行）和 `isSameAs`（第 623 行）不用改。`is()` 只在第 998、1002 行调用 `isSameMonth`、`isSameDay`。
- `src/` 里除 docblock 外没有别的 `->is(` 调用点。
- 若改 `$units` 循环，会影响所有走到这里的 tester。包括星期名（`Sunday`）、`next`/`last` 一类相对修饰、`noon`、`midnight` 等。
- 特别是 `$units` 里 `day`、`hour` 等同样存在“minimum 与当前值巧合”的类似风险，改动时要留意。

**【4 现有测试与约定】**
- `tests/Carbon/IsTest.php:1023-1057` 是 `testIs`，`tests/CarbonImmutable/IsTest.php:976` 起是镜像。
- 测试用的都是 `2019-06-02 12:23:45`，月份是 6、日是 2，所以碰不到“日为 1”这个触发条件。
- 与月份名相关的断言：
  - `:1037` `assertTrue(...->is('June'))`
  - `:1038` `assertFalse(...->is('May'))`
  - `:1055` `assertTrue(...->is('June 2019'))`
  - `:1056` `assertFalse(...->is('August 2019'))`
  - `:1057` `assertFalse(...->is('June 2018'))`
- 其他：
  - `:1041` `assertFalse(...->is('12:23:00'))`
  - `:1044` `assertFalse(...->is('12:00'))`
- 隐藏测试很可能在两个 IsTest 里各加一两条，例如 `Carbon::create(2023,10,1)->is('January')` 为 false。可能还会加 `'October'` 为 true。
- 没有发现外部规范。约定是 docblock 里的示例。
- 现有测试与题面期望不冲突。

**【5 边界与隐含要求】**
- 日为 1、月不同：10 月 1 日对 `January`。修复后，`2023-01-01` 对 `January` 必须仍为 true，`2023-01-15` 也必须为 true。
- 其他月份：`2023-10-01->is('February')` 等。其他月份的 1 日也可能误判，修复要覆盖所有月份。
- 缩写与大小写：`Jan`、`january`、`JANUARY`。
- 带年份的串：`January 2023`、`October 2023`。第 1029 行已经单独处理，但要保证不受影响。
- 同样的“minimum 巧合”可能出现在别的单位：
  - 时分秒：`midnight` 一类修饰是否会让 `hour` 等于 0。
  - 例如 `00:00` 且日期是 0 点整时的情形。
- 不变量：不能破坏 `June`、`Sunday`、`3pm`、`12h` 等已有行为。
- 不可变版本不能改变原对象。代码里用 `avoidMutation()` 处理，要保持。
- 时区、本地化月名这类题面没提，大概率不在要求内。

**【6 改动规模】**
- 1 个源文件，约 1 到 2 处，在 `is()` 的 `$units` 逻辑附近，属于局部修补。
- 测试也要加在两个 IsTest 文件里，每处几行。
- 不需要新增结构，不贯穿多层。

**【7 难点一句话】**
难点是定位：`$units` 循环里月份的 `minimum=1` 与“January”恰好相等，导致用 `startOf('year')` 比较，在日为 1 时误判。修复要改成不影响 `June`、`Sunday` 等已有 tester，又不引入新误判。