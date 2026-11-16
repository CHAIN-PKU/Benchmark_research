# 仓库档案：`Faker::Internet.password` 不含数字

## 【1 题面要点】
- **要求的行为**：`Faker::Internet.password` 生成的密码应当包含数字。
- **现状**：文档和注释的示例里有数字，但实现只用小写、大写和特殊字符。
- **复现**：题面给了 minitest 脚本。
  - 调用：`Faker::Internet.password(min_length: 8, mix_case: true)`。
  - 断言：`assert result.match(/[0-9]+/)  # returns nil if no matches`。
- **期望输出**，原话："I would expect that you are guaranteed to have a number for all permutations, or that there is an extra parameter to ensure numbers are included"。
- **修法建议**：只给了二选一的模糊说法。
  - 一是所有组合下都保证至少有一个数字。
  - 二是新增一个参数来保证数字。
  - 题面没有给参数名，也没有给期望的最小长度规则。
- **隐含的不确定点**：复现脚本在默认参数下要求出现数字，而且是"保证"，不是"大概率"。

## 【2 相关代码】
- `lib/faker/default/internet.rb:149` 是 `password(min_length: 8, max_length: 16, mix_case: true, special_characters: false)`，是唯一要改的实现。
  - `:150`：`max_length < min_length` 时抛 ArgumentError。
  - `:152-163`：按 `mix_case`（+2）和 `special_characters`（+1）累加 `required_min_length`。
  - `:165`：`min_length < required_min_length` 时抛错，文案是 "min_length should be at least N to enable mix_case, special_characters configuration"。
  - `:167`：`target_length = rand(min_length..max_length)`。
  - `:169-187`：先放一个必有小写，再按开关放一个必有大写、一个必有特殊字符，同时往 `character_bag` 里加字符。
  - `:189`：用 `character_bag` 补满长度。
  - `:191`：`shuffle(password).join`。
  - 全程没有数字，`character_bag` 里也没有 `0-9`。
- 文档注释在 `:128-146`。
  - 示例 `"Vg5mSvY1UeRg7"`、`"3k5qS15aNmG"` 都含数字，说明历史上数字是有的。
  - 注释 `:132-133` 写着"If true, at least one will be added"。
  - `@faker.version 2.1.3` 在 `:148`。
- `lib/faker.rb:241` 的 `shuffle`、`:245` 的 `rand` 用 `Faker::Config.random`，保证种子可复现。
  - `rand(max)` 在 `max.to_i` 不为正时返回 0。

## 【3 并列与牵连】
- 全仓库只有一个 `password` 实现，`lib` 下没有其他调用点。`Internet.user`（`internet.rb:545-548`）的文档示例里有 password，但那只是注释。
- 需要同步改动的文档：
  - `doc/default/internet.md:36-44`，示例同样含数字；如果新增参数，需要补说明。
  - `internet.rb:128-146` 的 YARD 注释。
  - `CHANGELOG.md` 通常由发布流程维护，未必要改。
- 最小长度的联动：
  - 如果数字变成强制要求，`required_min_length` 要加 1。
  - 这会影响 `:165` 的报错文案。
  - 也会影响现有测试里的小 `min_length`（见第 4 节）。
- 现有代码有一个小问题：`lower_chars[rand(lower_chars.count - 1)]` 用的是 `count - 1`。`rand(n)` 本身已经是 `[0, n)`，所以最后一个字符（`z`、`Z`、`*`）永远选不到。新增数字时如果照抄这个写法，`9` 也会选不到。
- 需要同样处理的并列实现：没有。

## 【4 现有测试与约定】
测试在 `test/faker/default/test_faker_internet.rb:119-243`。
- `:120`：`assert_match(/\w{3}/, @tester.password)`。
- `:127`、`:135`：`min_length` 从 1 到 32，传 `mix_case: false`，只检查长度范围。
  - `min_length: 1, mix_case: false` 在 `:163` 也出现，要求 `assert_match(/\w+/, password)`。
  - 这是关键冲突点：如果数字总是强制，`min_length: 1` 且不开 mix_case 就会被报错或放不下。
- `:148-160`：默认参数下要求至少一个大写和一个小写。
- `:184`：`mix_case: false` 时 `assert_match(/[^A-Z]+/, ...)`，这是弱断言。
- `:188`：`assert_match(/[!@#$%\^&*]+/, ...)`，特殊字符开启时必须出现。
- `:197-200`、`:213-216`：`min_length: 4` 或 3 配合 mix_case 加特殊字符，循环 16 到 32 次，必须有特殊字符和字母。
  - 如果数字也强制，`min_length: 3` 这条（`:213`）会冲突，因为 mix_case 加特殊字符已经要 3 个字符，再加数字要 4 个。
- `:221`：`assert_raise_message 'min_length should be at least 3 to enable mix_case, special_characters configuration'`，`min_length: 1` 时报错。
  - 报错文案写死了数字 3。如果数字被强制，隐藏测试可能改成 4，或保持不变。
- `:226-243`：`min_length` 为 1 或 2 时，`mix_case: value, special_characters: !value`。
  - `value = false` 时是 `min_length: 1`，`special_characters: true`，期望不抛错。
  - `value = true` 时是 `min_length: 2`，`mix_case: true`，期望不抛错。
  - 如果数字强制，这两条都会冲突。
  - `:235-243` 的确定性版本用 `deterministically_verify`（`test_helper.rb:34`，种子 `Random.new(42)`，多次结果必须一致）。
- 约定：
  - 外部规范没有。
  - 仓库约定是每个功能开关"开启则至少一个"，用 `required_min_length` 校验。
  - 随机性必须走 `Faker::Config.random`，可复现。
- 与题面的冲突：
  - 题面选项一（默认强制数字）与现有的小 `min_length` 测试直接冲突。
  - 选项二（新增参数，默认开启或关闭）冲突较小。
  - 隐藏测试的偏向不明。

## 【5 边界与隐含要求】
- 默认是否强制数字，决定了复现脚本能不能通过。脚本里没有传新参数，所以要通过，默认值必须产生数字。
- 如果新增参数，名字要猜，题面没给，隐藏测试可能直接用这个名字调用。常见猜法是 `digits`、`numbers`、`include_digits`，没有仓库依据。
- 默认是 `true` 时，要看 `min_length` 小的现有调用是否还通过：
  - `min_length: 1, mix_case: false`。
  - `min_length: 2, mix_case: true`。
  - `min_length: 3` 加 mix_case 加特殊字符。
- 数字的字符集用 `0-9`，注意 `rand(count - 1)` 导致 `9` 选不到的 off-by-one。
- `required_min_length` 要把数字计入，报错文案的 "enable ..." 列表也要包含新类型。
- 确定性：新增 `rand` 调用会改变同一种子下的输出，影响 `deterministically_verify` 的相互一致性。一致性只要求同种子同结果，不要求具体值，所以不受影响。
- 在 `mix_case: false` 且没有特殊字符时，必须仍至少含数字和小写。

## 【6 改动规模】
- 源码只改 1 个文件、1 个方法：`internet.rb:149-192`，局部修补，加约十行。
- 文档约 2 处：`internet.rb` 的 YARD 和 `doc/default/internet.md`。
- 现有测试大概率要改 2 到 4 处（`:163`、`:213`、`:221`、`:226-243`），加一条新测试。
- 不需要新增结构，也不贯穿多层。

## 【7 难点一句话】
代码改动本身很小，难在题面没说清默认是否强制数字和新参数叫什么，而强制数字会与现有的小 `min_length` 测试和报错文案冲突，所以要猜隐藏测试的取向。