**仓库档案：Faker `Internet.email(name:)` 生成连续点号**

**【1 题面要点】**
- 要求：`Faker::Internet.email(name: " Msgr. Titus Harvey")` 必须产出合法邮箱。
- 复现：3.4.1 得到 `"harvey.msgr..titus@russel-von.example"`，含连续两个点，不合法。3.3.1 得到 `"harvey_msgr_titus@corwin.example"`。
- 期望：“Factory should keep generating valid email addresses”。
- 题面没有给修法建议，也没有给精确的期望输出。
- 3.3.1 的分隔符是 `_`，3.4.1 是 `.`。所以随机分隔符和点号共同导致了这个问题。

**【2 相关代码】**
- `lib/faker/default/internet.rb:64-102` 的 `username(specifier:, separators:)`：
  - 第 67-71 行处理 String 参数：`specifier.gsub("'", '').split`，再 `shuffle`，然后 `join(sample(separators)).downcase`。
  - **这里是根源**：`split` 之后的 token 保留了 `"Msgr."` 里的句点，再用 `.` 连接就得到 `msgr..titus`。
  - 开头的空格会被 `split` 吃掉，所以不是问题。
  - 第 95-100 行是无参数分支，用 `Char.prepare` 清洗，所以不受影响。
- `internet.rb:33-49` 的 `email`：调用 `username`，再调用 `sanitize_email_local_part`，再 `construct_email`。
- `internet.rb:560-571` 的 `sanitize_email_local_part`：只把不在允许字符集里的字符替换成 `#`。`.` 在允许集里，所以不会被处理。它不检查首尾点号或连续点号。
- `lib/helpers/char.rb:5-9` 的 `Char.prepare`：`gsub(/[^\w-]/, '')`，会去掉点号。当前只用于无参数分支（`internet.rb:96-98`）。

**【3 并列与牵连】**
- `username` 的 String 分支会影响所有调用者：
  - `Internet.email`
  - `Internet.user`（`internet.rb:549`）
  - `lib/faker/default/omniauth.rb:15` 的 `Internet.email(name: self.name)`
  - `username` 的别名 `user_name`（`internet.rb:556`）
- `lib/faker/default/twitter.rb:126` 调用 `username(specifier: nil, ...)`，走无参数分支，不受影响。
- Integer 和 Range 分支会递归调用 `username(specifier: nil)`，也不受影响。
- 并列实现：`slug`（`internet.rb:441-446`）用 `words.delete(',.')` 去掉 `,` 和 `.`，可作为参考。
- 在 `username` 里修，会同时改变 `username` 的行为；只在 `email` 里修，则 `username` 仍可能返回 `msgr..titus`。两处都需要考虑。
- `separators` 由调用方传入，可以是 `+`、`-` 等，也可能是 `.`。

**【4 现有测试与约定】**
- `test/faker/default/test_faker_internet.rb:28-37`：`email(name: 'martín')` 断言 `assert_equal('mart#n', name)`。非法字符被替换成 `#`，而不是被去掉。如果在 `username` 里改用 `Char.prepare`，这个断言会失败。
- 第 39-45 行：`email(name: "Alexis O'Connell")` 配合 `assert_email_regex 'Alexis','OConnell', result`。
- `test/support/assert_email_regex.rb:13`：`/(first([_.])?last|last([_.])?first)@(.*)\.(example|test)/i`。
- 第 47-56 行：`separators: '+'` 断言 `(jane\+doe|doe\+jane)`。
- 第 78-87 行：`separators: '-'` 断言 `(ruby-faker|faker-ruby)`。
- 第 94-96 行：`username(specifier: "Alexis O'Connell")` 匹配 `/\A[a-z]+([_\.][a-z]+)*\z/`。
- 第 102-110 行：`'bo peep'` 匹配 `(bo(_|\.)peep|peep(_|\.)bo)`。
- 第 118-119 行：`username(specifier: 'Łucja')` 与 `'łucja'` 做 `assert_match`，所以非 ASCII 字符不能被去掉。
- 第 506 行：`slug(words: 'Foo.. bAr., baZ,,')` 匹配 `/^foo(_|\.|-)bar(_|\.|-)baz$/`。
- 确定性测试：`test_helper.rb:35-43` 的 `deterministically_verify` 固定种子为 42。`shuffle` 和 `sample` 的调用次数和顺序若改变，会影响 `faker ruby` 这类测试的可预期输出。
- 外部规范是 RFC 5322 的 dot-atom：本地部分不能有连续点号，也不能以点号开头或结尾。仓库里没有明确约定。
- 与题面不冲突。隐藏测试大概率是 `email(name: "...")` 加上“不含 `..`”或合法邮箱正则的断言。

**【5 边界与隐含要求】**
- 带点号的 token：`Msgr.`、`Jr.`、`Dr.` 等称谓。
- 点号出现在中间：`J.R.R.`、`a.b c`。
- 全由点号组成的 token：`"..."` 去掉后会变空，造成空 token 和连续分隔符。
- 首尾点号：本地部分不能以 `.` 开头或结尾，包括处理后产生的情况。
- 分隔符本身为 `.` 时，要避免和 token 里的点号叠加。
- 其他连续标点：`-` 或 `_` 连着出现虽然合法，但风格上不好看。
- `email` 里用户传入的 `separators` 也可能是点号。
- 保留现有行为：`martín` → `mart#n`、`Łucja` → `łucja`、`+` 和 `-` 分隔符，以及撇号被去掉。
- 空名字或全标点名字：处理后可能得到空本地部分。
- 修复后不能破坏 seed 42 下的确定性。

**【6 改动规模】**
- 只需改 `lib/faker/default/internet.rb` 一个文件，局部修补，1-2 处：
  - `username` 的 String 分支：对 token 去掉点号，或对结果合并连续分隔符。
  - 可选：`sanitize_email_local_part` 里做收尾（压缩 `..`、去掉首尾 `.`）。
- 另外需要在 `test/faker/default/test_faker_internet.rb` 加测试。
- 不需要新增结构，也不贯穿多层。

**【7 难点一句话】**
根因很容易定位，但修的位置有取舍：既要消除连续点号和首尾点号，又不能破坏 `martín→mart#n`、`Łucja→łucja` 等现有断言和固定种子下的确定性；隐藏测试具体断言什么（只是“无 `..`”，还是精确输出）题面没有说明。