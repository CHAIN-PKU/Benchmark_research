**档案:Style/FileNull 把任意 `'nul'` 当成空设备**

**【1 题面要点】**
- 期望行为:`foo('nul')` 这类字符串不应被报告。issue 原文写的是 "Ignore `'nul'` strings in code."
- 实际行为:`Style/FileNull: Use File::NULL instead of nul.`,报在 `expect(subject.parse_char_or_int('nul')).to eq(0x00)` 上。
- 复现:最小例子是 `test.rb` 里写 `foo('nul')`,再执行 `bundle exec rubocop test.rb`。
- 题面没给修法建议,也没给期望输出的具体形式。
- 要求本身有歧义:"忽略所有 nul" 只是用户的期望,不一定是最终语义。例如孤立的 `path = 'nul'` 是否仍要报,题面没说。

**【2 相关代码】**
- `lib/rubocop/cop/style/file_null.rb:42`:`REGEXP = %r{\A(/dev/null|NUL:?)\z}i`,带 `i` 标志,所以 `nul`、`Nul` 都会匹配。`NUL:?` 的冒号可选。
- `file_null.rb:45-55`:`on_str` 取 `node.value`,依次判断 `invalid_string?`、`acceptable?`、`REGEXP.match?`。命中则报 offense,并把节点替换成 `File::NULL`。
- `file_null.rb:59-61`:`invalid_string?` 排除空串和无效编码。
- `file_null.rb:63-69`:`acceptable?` 在父节点为 array 或 pair 时放行。
- `file_null.rb:42-43` 的 `MSG` 是 `Use File::NULL instead of %<source>s`。
- `config/default.yml:3950-3954`:该 cop 是 `Enabled: pending`、`SafeAutoCorrect: false`、`VersionAdded: '1.69'`,描述为 `Use File::NULL instead of hardcoding "dev/null"`。
- 文档注释在 `file_null.rb:6-38`。

**【3 并列与牵连】**
- 没有并列实现。`grep FileNull` 只命中 cop 本身、spec、`default.yml`、docs、CHANGELOG 和 relnotes。
- `docs/modules/ROOT/pages/cops_style.adoc:5146` 的文档由 cop 类注释生成。若改了注释里的 `@example`,文档要同步重新生成,仓库通常有检查文档是否一致的 rake 任务。
- `changelog/` 目录里是 `fix_*.md` 这类条目,按约定新增一个。
- cop 只有 `on_str` 一个入口,没有成对方法。`dstr` 里的 `str` 子节点也会进 `on_str`。
- 没有其他调用点或其他 cop 依赖它。

**【4 现有测试与约定】**
- `spec/rubocop/cop/style/file_null_spec.rb:27-36`:`'NUL'` 要报,并修正为 `File::NULL`。
- `file_null_spec.rb:38-47`:`'NUL:'` 要报。
- `file_null_spec.rb:49-61`:`it 'is case insensitive'` 断言 `file = "nul"` 要报:`^^^^^ Use File::NULL instead of nul.`;`"/DEV/NULL"` 也要报。
- `file_null_spec.rb:63-91`:子串、数组、`%w[]`、hash 的 key 和 value 都不报。
- 与题面可能冲突:`file_null_spec.rb:49-61` 明确要求小写 `nul` 要报。
  - 若按"所有 nul 都忽略"来改,这条测试必须改或删。
  - 若改成"仅排除作为方法参数的字符串",该测试仍可通过。
- 外部规范:Ruby 的 `File::NULL` 在 Windows 上是 `"NUL"`,Unix 上是 `/dev/null`。仓库里没有其他约定可参照。

**【5 边界与隐含要求】**
- 大小写取舍:`nul` 是否仍要报,`NUL` 是否仍要报。
- 没有 `NUL:` 的光秃 `nul`、`NUL` 容易误报。带冒号的 `NUL:` 和 `/dev/null` 几乎不会有歧义。
- 如果按语境限制(例如只在赋值或特定调用里报),要处理 `foo('nul')`、`x = 'nul'`、`File.open('nul')`、`a == 'nul'`、返回值等不同位置,取舍不清楚。
- 多个测试要一起改:大小写不敏感那条,以及新增 `foo('nul')` 不报的断言。
- 保持 dstr、heredoc、符号等原有行为不变。
- 文档的 `@example` 和 `# ok` 注释要同步,`default.yml` 的描述也可能需要更新。

**【6 改动规模】**
- 约 3 个文件、4 到 6 处:`file_null.rb` 的正则或判断逻辑、`file_null_spec.rb` 的测试、一个新的 changelog 条目,可能还有文档注释。
- 属于局部修补,不需要新增结构,也不需要贯穿多层。
- 改动本身很小(一行正则或一个判断)。

**【7 难点一句话】**
代码改动很小,难点在于判断隐藏测试要的语义:是整体不再匹配裸 `nul`,还是只按语境放行。现有 spec 里 `"nul"` 要报的断言可能和这个期望冲突,要选对取舍。