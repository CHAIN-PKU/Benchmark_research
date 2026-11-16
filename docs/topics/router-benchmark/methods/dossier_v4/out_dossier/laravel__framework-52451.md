**档案：Custom rule 失败时，自定义消息数组污染 MessageBag**

我读了 `FormatsMessages.php`、`Validator.php` 和 `ClosureValidationRule.php`，也看了 `tests/Validation` 里与自定义规则相关的测试。我没有运行任何代码，下面的结论都来自读代码。

**【1 题面要点】**
- 要求的行为：当 `$messages` 里按属性嵌套定义了消息（`'bar' => ['required' => ..., 'numeric' => ..., 'gt' => ...]`）时，闭包规则或规则类失败，错误仍应是 `attribute => [msg]`。
- 期望输出：`"bar" => ["bar must be odd"]`。
- 实际输出：多出 `required`、`numeric`、`gt` 三个顶层键，值是 bar 的自定义消息原文。
- 题面给了完整复现（rules、messages、data）和期望输出，没有给修法建议。

**【2 相关代码】**
- `src/Illuminate/Validation/Validator.php:853-886`，`validateUsingCustomRule`：
  - 第 874 行 `$messages = $this->getFromLocalArray($attribute, $ruleClass) ?? $rule->message();`
  - 第 878-884 行把 `(array) $messages` 逐项遍历，`is_string($key) ? $key : $attribute`，再 `messages->add($key, ...)`。
  - 这一步是 bug 的出口。
- `src/Illuminate/Validation/Concerns/FormatsMessages.php:99-137`，`getFromLocalArray`：
  - 查找键依次为 `"{attr}.{rule}"`、`rule`、`attr`。
  - 第 129 行只有在 `$message[$lowerRule]` 存在时才返回子项，否则返回整个 `$message`。
  - 闭包规则的 `$ruleClass` 是 `ClosureValidationRule`，bar 数组里没有这个键。
  - 于是 `bar` 键命中，整个 `['required'=>..., 'numeric'=>..., 'gt'=>...]` 被返回。
  - 它不是 null，所以 `?? $rule->message()` 不会触发。
  - 随后第 878 行起把它当作 `key => message` 列表，字符串键 `required`、`numeric`、`gt` 就成了顶层错误键。
- `FormatsMessages.php:22-73`，`getMessage`：标准规则的消息路径，并不走 `validateUsingCustomRule`。
- `FormatsMessages.php:82-89`，`getInlineMessage`：针对 size 规则处理数组条目。
- `ClosureValidationRule.php:59-80`：`message()` 返回 `$this->messages`，这是闭包里 `$fail` 收集的消息。

**【3 并列与牵连】**
- `getFromLocalArray` 的调用点：
  - `FormatsMessages.php:84`（`getInlineMessage`）
  - `FormatsMessages.php:70`（用 `fallbackMessages`）
  - `Validator.php:874`
  - 修在 `getFromLocalArray` 里会同时影响标准规则的消息路径，风险更大；修在 `validateUsingCustomRule` 里则只影响自定义规则。
- `Rules/Password.php:321` 和 `Rules/File.php:256` 也用 `$this->validator->customMessages`，是并列的消费方。我没读它们的细节，但它们是同一类 `validateUsingCustomRule` 路径的使用者，修复后行为需要保持一致。
- `InvokableValidationRule` 的 `$ruleClass` 取的是 `get_class($rule->invokable())`，不同于闭包的 `ClosureValidationRule`，同样会走第 874 行。
- 第 881-883 行用 `$key` 作为 `makeReplacements` 的 `$attribute`，是已有的"消息数组带字符串键"的支持。这个路径必须保留。

**【4 现有测试与约定】**
- `tests/Validation/ValidationValidatorTest.php:7845` 起的 `testCustomValidationObject` 断言了：
  - 第 7892 行 `assertSame('name must be taylor', $v->errors()->all()[0])`
  - 第 7923 行 `assertSame('name was adam instead of taylor', ...)`
  - 第 7960-7962 行：`states.0`、`states.1`、`number` 的消息。
  - 第 7964 行起是"规则 `message()` 返回数组"的情形。这个用例我只读到开头，数组消息具体怎么断言我没看全。
- 我没有找到现有测试把 `$messages` 里的嵌套数组条目和自定义规则组合起来，所以这是新增场景。
- 约定：嵌套数组 `attr => [rule => msg]` 是标准规则的自定义消息格式，`getFromLocalArray` 第 129 行的 `isset($message[$lowerRule])` 已经体现。
- 与题面期望没有冲突。`getFromLocalArray` 针对自定义规则类的"类名作为键"这一用法，现有测试里我没查到。

**【5 边界与隐含要求】**
- 嵌套数组里没有当前规则对应的键时，应回退到 `$rule->message()`，而不是返回整个数组。
- 通配符键（`bar.*`）命中时：第 116 行有类似的 `isset($message[$lowerRule])` 判断，没命中同样会返回整个数组，需要一并考虑。
- 嵌套数组里恰好有 `ClosureValidationRule` 或自定义规则类名对应的键时，应当仍然生效（`getFromLocalArray($attribute, $ruleClass)` 的现有用途）。
- 数组消息的 `message()` 返回值（带字符串键）的现有行为不能破坏。
- `getFromLocalArray` 的 `$lowerRule` 参数在这里传的是原始类名，没有 `Str::snake`。我没有核实这是否影响匹配。

**【6 改动规模】**
- 1 个源文件、1 到 2 处，局部修补：`Validator.php:874` 一带，或 `getFromLocalArray` 的返回逻辑。
- 另需在 `ValidationValidatorTest.php` 加一个回归测试。
- 不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
定位不难，难点是在 `getFromLocalArray` 这个共用函数和 `validateUsingCustomRule` 之间选对修复位置，既不破坏标准规则的消息解析，也不破坏带字符串键的数组消息和类名键的现有行为。