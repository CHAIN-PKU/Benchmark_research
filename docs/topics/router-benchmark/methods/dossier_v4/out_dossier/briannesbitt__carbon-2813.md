**Carbon 仓库档案：实现 `Psr\Clock\ClockInterface`**

**【1 题面要点】**
- 题面只有一句话："Allow to use `Carbon\FactoryImmutable` where `Psr\Clock\ClockInterface` is expected."
- 题面没有复现、期望输出，也没有修法建议。
- 隐含要求：`FactoryImmutable`（最好连 `Factory` 一起）的实例要能通过 `instanceof Psr\Clock\ClockInterface`，并提供 `now(): DateTimeImmutable`。

**【2 相关代码】**
- `src/Carbon/Factory.php:242` 的 `class Factory`：
  - 没有 `implements`。
  - 属性是 `$className`（244 行）和 `$settings`（246 行）。
  - `__construct` 在 248 行。
  - `__call`（298 行）用 `ReflectionMethod($this->className, $name)` 反射转发静态方法，并套用 settings（timezone 等）。目前 `$factory->now()` 靠它走到 `Carbon::now($tz)`。
- `src/Carbon/FactoryImmutable.php`：只有 `protected $className = CarbonImmutable::class;`，没有别的内容。
- `src/Carbon/Traits/Creator.php:257` 的 `static now($tz = null)`：返回 `new static(null, $tz)`。它不带返回类型，尊重 `setTestNow`（`Traits/Test.php:64`）。
- `composer.json:42`：`require` 里没有 `psr/clock`。
- `composer.json:43`：php 是 `^7.1.8 || ^8.0`。

**【3 并列与牵连】**
- `Factory` 与 `FactoryImmutable` 是并列的。`ClockInterface::now()` 返回 `DateTimeImmutable`，所以：
  - `FactoryImmutable::now()` 直接返回 `CarbonImmutable`，它是 `DateTimeImmutable` 的子类，满足接口。
  - 如果可变的 `Factory` 也实现接口，`now()` 会返回可变的 `Carbon`，不满足接口。此时要么只让 `FactoryImmutable` 实现，要么 `Factory` 里转成不可变对象。
- 在类上新增真实的 `now()` 方法，会绕过 `__call` 的反射转发。因此要自己处理 `settings`（locale、timezone）和 `$tz` 参数。
- 子类 `MyCarbon` 之类的自定义 `className` 要继续可用。
- 不影响 `Carbon::now`。
- `Factory.php` 头部有 `@method ... now()` 的 autodoc 注释块，由 `build.php` 生成，可能需要同步。
- 如果 `Factory` 多了真实的 `now` 方法，PHPStan 扩展（`extension.neon`、`src/Carbon/PHPStan`）也可能受影响。

**【4 现有测试与约定】**
- `tests/Factory/FactoryTest.php:30-48` 里的断言只测 `parse` 的格式、`locale` 和 `assertInstanceOf(CarbonImmutable::class, $factory->parse(...))`。
- `FactoryTest.php:51` 起的 `testFactoryModification` 测 `className()`、`settings()`、`mergeSettings()` 的 getter/setter。
- 没有任何测试涉及 Clock 或 `now`。
- `tests/CarbonImmutable/StringsTest.php:58` 用到了 `FactoryImmutable`。
- 仓库里没有任何 `psr/clock` 或 `Psr\Clock` 的引用，我也没找到 `vendor` 目录。
- 外部规范是 PSR-20：`ClockInterface::now(): DateTimeImmutable`。接口在 `psr/clock` 1.0 里，有返回类型。
- 与题面不冲突，但是新增依赖。

**【5 边界与隐含要求】**
- 依赖：要在 `composer.json` 里加 `psr/clock`。接口的存在不能想当然，因为 `vendor` 里没有它。
- PHP 版本：库支持 PHP 7.1.8 起，而 psr/clock 的版本要求可能比这高。需要选好版本约束（`^1.0`，且 psr/clock 1.0 要求 php >=8.0）。
  - 用 `require` 还是 `suggest`/`conflict`，要和 7.1 兼容性一起想。
  - 常见做法是让接口可选，例如用 `if (interface_exists(...))` 或用 trait 加条件声明，保证没装 psr/clock 时不报错。
- `now()` 的签名要和接口兼容：`public function now(): DateTimeImmutable`。
  - 带 `?string`/`$tz` 之类的可选参数是可以的，因为 PHP 允许子类扩展可选参数。
  - 但返回类型必须是 `DateTimeImmutable` 或其子类。
  - 返回类型声明在 PHP 7.1 下可以用。
- 要尊重 `setTestNow`，要套用 settings（timezone/locale）。
- 如果 `className` 被改成可变的 `Carbon`，`now()` 要保证仍返回 `DateTimeImmutable`。

**【6 改动规模】**
- 约 2 到 4 个文件：`Factory.php` 或 `FactoryImmutable.php`、`composer.json`，可能还有 `tests/` 和文档。
- 属于局部修补，加一个方法和一个 `implements`。
- 难点主要在依赖和版本兼容的处理，而不是代码量。

**【7 难点一句话】**
代码本身只是加一个 `now()` 并声明 `implements`，难点是 psr/clock 在 `vendor` 里不存在、库又要支持 PHP 7.1，所以要处理接口的可选依赖，并让 `now()` 的签名、返回类型和 settings 行为同时满足接口。