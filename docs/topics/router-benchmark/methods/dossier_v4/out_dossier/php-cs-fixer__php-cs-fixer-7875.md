【1 题面要点】
- 要求的行为：`statement_indentation` 不应改动类里多行的 `const` 声明。题面原文是 "`statement_indentation` erronously "fixes" multiline consts."
- 复现：给了。输入如下，期望是原样保留。
  ```php
  class Foo
  {
      protected const
          FOO = 'Bar',
          BAR = 'Foo';
  }
  ```
- 实际输出：第二个常量被改成 `    BAR = 'Foo';`，即从 8 格缩进变成 4 格。
- 题面没有给修法建议，也没有明说期望输出，需要自己从"不应修改"推出来。
- 版本是 3.51.0。

【2 相关代码】全部在 `src/Fixer/Whitespace/StatementIndentationFixer.php`，共 797 行。
- `applyFix` 在 122-574 行，是主循环，用 `$scopes` 栈维护缩进作用域。
  - 356-360 行：`$methodModifierTokens`（public/protected/private/static/abstract/final）直接 `continue`，不建 statement scope。
  - 553-572 行：遇到非空白、非 `; , }` 的 token 时，若当前不是 statement/block_signature scope，就调 `findStatementEndIndex` 建 `type=statement` 的 scope。`initial_indent` 和 `new_indent` 取自上一行。`const` 就是这样开了一个 statement scope。
  - 503-509 行：在 statement scope 内遇到换行空白时，只把 `initial_indent` 替换成 `new_indent`，所以相对缩进被保留。
  - 425-501 行：在 block 内遇到换行空白时，直接重写成 `initial_indent` 加一级 indent。
  - 543-551 行：当 `$index >= end_index` 时弹出 scope。
- `findStatementEndIndex` 在 576-653 行。
  - 613 行：`;`、`,`、`}`、`T_CLOSE_TAG` 都被当作语句结束。
  - 647 行：`$endIndex = getPrevNonWhitespace($searchEndIndex)`。
- 推测的成因：`const\n FOO = 'Bar',` 的 statement scope 在第一个逗号前结束。逗号之后的换行落回外层 class block，被重写成 4 格。所以只有第二个及之后的常量行被改坏，第一个常量因为还在 statement scope 内而保留。
- 逗号被当成结束符，大概是为了处理数组元素、参数列表等场景。这一点是推测，我没有在代码里找到注释或测试来印证。

【3 并列与牵连】
- 同类写法在类里是多属性声明 `public $a,\n $b;`，以及 `static $a,\n $b;`、`global $a,\n $b;`。它们走同一条路径，很可能有同样的问题。
- `findStatementEndIndex` 只有两个调用点：222 行（无花括号控制结构的块）和 558 行（statement scope）。改这个函数的逗号逻辑，会同时影响这两处。
- 逗号作为结束符会影响很多场景：
  - 无花括号 `if/else/foreach` 的主体，由 222 行调用。
  - 类外顶层的 `use A,\n B;`。
  - 表达式里的逗号。
- 在 `(`、`{`、数组方括号内的逗号被 600-611 行跳过，所以不受影响。
- 不要把修复做成只针对 `T_CONST` 的特判，否则漏掉属性等并列情形。
- `bracesFixerCompatibility` 分支（267-275、416-423 行）只处理函数闭包和注释，不涉及此处。

【4 现有测试与约定】
- 测试文件是 `tests/Fixer/Whitespace/StatementIndentationFixerTest.php`，约 1340 行以上，只有 `provideFixCases`、`provideFixWithTabsCases`、`provideFixPhp80Cases`、`provideFixPhp81Cases` 四个数据提供者。
- 我的 grep 没有找到含 `const` 的用例，也没有找到多属性逗号声明的用例，所以这个行为目前没有任何测试覆盖。
- 逗号相关的现有用例都是参数、数组一类的列表。例如 131、137、146、152 行是 `$bar,` 与 `     $bar,` 这类缩进；383-411 行有 `$foo,` 与单独成行的 `,`。这些用例的缩进约定必须保持不变。
- 测试写法：`$this->doTest($expected, $input)`，在 `testFix` 里调用，位于测试文件第 41 行附近。隐藏测试大概率是在 `provideFixCases` 里新增 `yield`，期望输出与输入相同，也可能带一个缩进有误的输入。
- 约定：没有外部规范，行为由现有测试决定。题面期望（保留作者的多行缩进）与现有测试没有明显冲突，但具体"保留"还是"规范化到某个缩进"题面没说，我也没找到约定。

【5 边界与隐含要求】
- 修饰符不止 `protected`：`public const`、`private const`、`final public const`，以及无修饰符的 `const`。
- 带类型的常量（PHP 8.3）：`const string FOO = 'a',\n BAR = 'b';`。
- 常量值本身多行，比如数组值或含逗号的表达式。
- 两个以上的逗号。
- `const` 在 enum、interface、trait 里。
- 类外的顶层 `const A = 1,\n B = 2;`。
- 属性多声明 `public $a,\n $b;`，题面没提，但机制相同。
- 用 tab 缩进的情况，对应 `provideFixWithTabsCases`。
- 逗号后紧跟注释的情况。
- 不能破坏现有列表类逗号用例，尤其是 383-411 行那些奇怪的单独逗号写法。

【6 改动规模】
- 源码大概率只改一个文件，`StatementIndentationFixer.php`，改动在 `findStatementEndIndex` 或 558 行附近的 statement scope 建立逻辑，几行到十几行。
- 测试方面是在测试文件新增若干用例。
- 属于局部修补，不需要新增结构，也不贯穿多层。
- 例外：如果要同时修属性、`use`、`global` 的逗号情形，会稍大一些。

【7 难点一句话】
- 难在 `findStatementEndIndex` 把 `,` 一律当作语句结束符，这对参数列表、数组之类是对的，对 `const`/属性的逗号分隔声明是错的；需要在不破坏上述现有逗号用例的前提下，区分出"这个逗号属于同一条 const 声明"，并想清楚多行续行应该保持什么缩进。

注：我没有实际运行测试或复现，上面的成因是读代码得出的推断。