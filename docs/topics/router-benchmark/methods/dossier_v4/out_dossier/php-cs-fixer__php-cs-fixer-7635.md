**档案：`fully_qualified_strict_types` 同名异命名空间符号被误缩短**

**【1 题面要点】**
- 期望行为：已有 `use App\Actions\CreateUrl;` 时，不能把 `App\Actions\Folder1\CreateUrl::run()` 和 `App\Actions\Folder2\CreateUrl::run()` 缩成 `CreateUrl::run()`。三者指向不同的类，缩短会改变语义。
- 复现：给了 Before/After 两段 PHP 片段。
- 期望输出：只有 Before 本身，即这三行都应保持不变。
- 没有给修法建议，也没给命名空间声明和完整上下文。
- 题面片段里长名没有前导反斜杠，也没说明文件所在的命名空间。
- 因此触发条件需要自己推断：很可能是文件在 `App\Actions` 命名空间下，或写的是 `\App\Actions\Folder1\CreateUrl`。
- 该 issue 引自 #7619，是 v3.42 引入的回归。

**【2 相关代码】**（全部在 `src/Fixer/Import/FullyQualifiedStrictTypesFixer.php`，共 708 行）
- `applyFix` :222。遍历每个命名空间，构建 `$uses`（`normalised 全名 => 短名`，:232-235）。按 token 种类分发到 `fixFunction`、`fixExtendsImplements`、`fixCatch`、`fixClassStaticAccess`（`::`）和 `fixPhpDoc`。
- `fixClassStaticAccess` :393。向前收集 `::` 左侧的名称，交给 `shortenClassIfPossible`。题面场景走这条路径。
- `shortenClassIfPossible` :416-458。**最可能出问题的地方**，有三个分支：
  - :428 的 `$uses` 精确命中。
  - :431 的全局命名空间分支，这里有 `$inUses` 短名冲突检查（:436-446）。
  - :448-456 的「以当前命名空间为前缀就去掉前缀」分支，**没有任何与 `$uses` 短名冲突的检查**。
- `determineShortType` :497-552。供类型声明和 phpdoc 使用，已有冲突检查（:538-546）：
  ```
  // if short names are the same, but long one are different then it cannot be shortened
  foreach ($uses as $useLongName => $useShortName) { if (strtolower($typeNameShort)===strtolower($useShortName) && strtolower($typeName)!==strtolower($useLongName)) return null;
  ```
  这说明 `shortenClassIfPossible` 缺的就是这段逻辑。
- `replaceClassWithShort` :557。实际改写 token。
- `registerSymbolForImport` :667。`import_symbols` 开启时用，已有短名冲突回避（:684-691）。

**【3 并列与牵连】**
- `shortenClassIfPossible` 服务于三个调用点：`fixExtendsImplements`（:342）、`fixCatch`（:374）、`fixClassStaticAccess`（:405）。改它会同时影响 extends/implements、catch 和 `::`。
- `determineShortType` 与 `shortenClassIfPossible` 是并列的两套缩短逻辑。前者已处理冲突，后者没有。可以抽取共用逻辑，也可以只在后者补检查。
- 疑点：`determineShortType` :506 的 `isset($uses[...]) && ($withLeadingBackslash || '' === $namespaceName)` 条件，与 `shortenClassIfPossible` 的行为不完全一致。不要想当然地互相照搬。
- `fixPhpDoc` :299 的正则只匹配简单类型。
- 下游：本 fixer 优先级为 7，必须在 `NoSuperfluousPhpdocTagsFixer`、`OrderedImportsFixer`、`StatementIndentationFixer` 之前运行，必须在 `PhpdocToReturnTypeFixer` 之后运行。

**【4 现有测试与约定】**（`tests/Fixer/Import/FullyQualifiedStrictTypesFixerTest.php`）
- :1018-1028，类型声明场景已有同名异命名空间保护：
  ```
  namespace Foo; use Bar\TheClass; ... __construct(\Foo\TheClass $x)
  ```
  期望不变。
- :500-504，`import_symbols` 冲突：`use Other\A; function foo(A $a, \YetAnother\A $b)` 不变。
- :128-130，全局命名空间下反斜杠保留：`use A\Exception; ... \Exception $e2`。
- :394 和 :411，静态调用只测了 `StaticFunctionCall::bar()` 与 `\Other\StaticFunctionCall::bar()` 的 import 场景。
- :334-348，`A::class` 和 `\ZXY\A::class` 的缩短。
- 未找到 `::` 或 catch 或 extends 在冲突场景下的测试，覆盖空白在这里。
- 与题面不冲突：已有的类型声明行为和题面期望一致，只是 `::` / catch / extends 没有同样的保护。
- 约定：参考实现就是同文件的 `determineShortType`。

**【5 边界与隐含要求】**
- 比较要大小写不敏感（PHP 类名不区分大小写，`$uses` 键已是小写）。
- 带 `use X as Y` 别名的情况。`$uses` 存的是别名，冲突判定要用别名而不是原名。
- 题面中没有前导反斜杠的写法（`App\Actions\Folder1\CreateUrl`）。
  - 当前 `shortenClassIfPossible` 只处理以 `\` 开头的名称，需要确认在题面场景下是哪条路径触发的。
  - 如果触发点是别处，修复位置可能不同。
- 命名空间等于类型全名前缀的边界（:449 的 `!==` 判断）。
- 全局命名空间分支已有冲突检查，不应被改坏。
- 多命名空间文件里 `$uses` 按命名空间独立。
- `import_symbols=true` 时，`registerSymbolForImport` 会往 `$uses` 里伪造条目（:697-698）。冲突检查可能把刚注册的符号当成已有 use，需确认不产生干扰。
- 同一个 `$uses` 中完全相同的长名应仍能缩短（长名相等时不算冲突）。

**【6 改动规模】**
- 源码 1 个文件、1 到 2 个函数，局部补丁。
- 最小方案是在 `shortenClassIfPossible` :448-456 分支补一个冲突检查，约 10 行。
- 更整洁的方案是把冲突检查抽成私有方法，让两处共用。
- 测试要补 `::`、catch、extends 的冲突用例。
- 不需要新增结构，也不涉及多层。

**【7 难点一句话】**
- 难点主要在定位：题面没给命名空间，要判断 `shortenClassIfPossible` 的前缀分支（:448）才是缺冲突检查的位置。
- 补丁本身很小，能照搬 `determineShortType` :538-546。
- 隐藏测试可能覆盖 catch、extends、`::` 多个调用点，以及别名、大小写，所以只改一个调用点或漏掉别名都会失败。