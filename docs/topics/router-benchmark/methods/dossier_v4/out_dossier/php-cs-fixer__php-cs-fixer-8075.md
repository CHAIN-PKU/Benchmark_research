**档案：PhpUnitAttributesFixer 对同一注解多次出现（`@group`）只转换一个**

**【1 题面要点】**
- 要求的行为：同一个类或方法的 docblock 里，同名注解出现多次时（例子是两个 `@group`），每个都要转成对应的 `#[Group(...)]` 并从 docblock 删除。
- 当前行为：只转换了最后一个（`sqlite`），`@group database` 留在了 docblock 里。
- 复现：有，是 DBSqliteTest 的类 docblock 前后 diff。
- 期望输出：有。
  - 两条属性按原顺序输出，先 `#[Group('database')]`，再 `#[Group('sqlite')]`。
  - 两个 `@group` 都从 docblock 删除。
  - 题面没有给修法建议。
- 题面期望的 docblock 里，原有的说明文字和 ` *` 空行会保留。

**【2 相关代码】**（均在 `src/Fixer/PhpUnit/PhpUnitAttributesFixer.php`）
- `applyPhpUnitClassFix`（:90-143）：主循环。
  - 对每个 docblock 用 `array_reverse($docBlock->getAnnotations())` 倒序遍历（:112）。
  - 每个注解调用 `fixingMap` 里对应的方法得到 `$tokensToInsert`，再 `insertSlices([$index+1 => ...])`，最后 `$annotation->remove()`。
- **根因几乎可以确定在 `isAttributeAlreadyPresent`（:208-249）**。
  - 它检查 docblock 后面的属性里是否已有同一个类。
  - 它只比较类的全限定名（:216-246，`$insertedClassName === $className`），不比较参数。
  - 倒序处理时，先转换 `sqlite` 并插入 `#[Group('sqlite')]`。再处理 `database` 时，紧跟 docblock 的属性已经是 `Group`，类名相同，于是返回 true，走到 :125-127 的 `continue`。这样既不插入也不 `remove()`。
- `fixWithSingleStringValue`（:262-279）：`group`、`testDox`、`ticket` 用它生成属性。
  - 它用正则 `@group\s+(.*\S)(?:\R|...)` 从 `$annotation->getContent()` 取值，所以每个注解单独取值应该没问题。
- `createAttributeTokens`（:520-546）：生成 `#[\PHPUnit\Framework\Attributes\X(...)]`，前面带一个克隆的空白 token。

**【3 并列与牵连】**
- 同样的问题会影响所有"同一注解可重复出现"的情况，不止 `@group`。
  - `@covers`、`@uses`、`@depends`、`@dataProvider`、`@testWith`、`@requires`、`@ticket` 等都走同一个去重检查。
  - 例如多个 `@depends` 或多个 `@requires` 在方法上也会漏转。
- 现有测试 :91-113 依赖这个去重：docblock 里已有同类属性时，就不再转换，也不删除注解。
  - 修的时候要区分"用户原本就写了的属性"和"本次循环刚插入的属性"。
- 可能的做法是比较参数，或只对原有属性做检查。这里只做并列分析，不展开方案。
- 修改限于这个 fixer。`DocBlock`/`Annotation::remove` 属于共享代码，不必改。

**【4 现有测试与约定】**
- `tests/Fixer/PhpUnit/PhpUnitAttributesFixerTest.php:423-426`：`handle Group` 用例，`createCase(..., "#[Group('groupName')]", '@group groupName')`，只覆盖单个 `@group`。
- :91-102：`do not fix when there is already attribute of related class`。
  - 已有 `RequiresPhp('^7.1')`，docblock 里是 `@requires PHP ^8.2`，期望原样不动。
  - **这条与"只比较参数"的修法有冲突**：参数不同（`^7.1` 与 `^8.2`），按参数比较就会被转换。
  - 所以不能简单改成比较参数，需要保留"属性类已存在就跳过"，只对同一次运行内新插入的属性放行。
- :104-113：`do not duplicate attribute when used without leading slash`，已有 `#[PHPUnit\Framework\Attributes\RequiresPhp('^6.1')]`，docblock 里是 `@requires PHP ^6.1`，期望不重复生成。
- :115 起：`do not duplicate attribute when used with import`，同样的约束。
- 没有测试覆盖多个同名注解，隐藏测试大概率会在这里新增。
- 外部规范：PHPUnit 的 `Group` 属性本身可重复，题面也支持这一点。

**【5 边界与隐含要求】**
- 输出顺序必须是源码里的原顺序：`database` 在前，`sqlite` 在后。
  - 当前倒序处理，每次都插到 `$index+1`，所以后处理的会排在前面。
  - 这个顺序在两个以上同名注解时尤其容易出错。
- 类级和方法级都要工作：`$annotationScope` 区分 class 和 method。
- docblock 清理：删除后若 docblock 只剩空壳，要整体清除（:137-138），否则保留说明文字（题面示例就保留了）。
  - 期望输出里 `*` 空行也被清理成了一个。
  - 这可能受 `Annotation::remove` 和 docblock 行处理影响，需要看测试里的精确空白。
- 与已有属性并存：用户已有 `#[Group('x')]`，docblock 里又有 `@group y`、`@group z`。
  - 现有逻辑会直接跳过，这是否算对，题面没说。
  - 还要保证不要把本次新增的当成原有的。
- 重复值，例如两个相同的 `@group a`，是否去重：题面没有说明。

**【6 改动规模】**
- 只改 1 个文件，约 1-2 处。
  - 主要在 `isAttributeAlreadyPresent` 或其调用处，比如缓存原有属性、只检查循环开始前已存在的属性。
  - 为了顺序，可能还要调整插入位置。
- 属于局部修补，不需要新增结构，也不贯穿多层。
- 另需在测试文件里加 1 到几个用例。

**【7 难点一句话】**
根因容易定位，难在去重要同时满足三点：用户原有的同类属性仍要跳过（:91-113 的现有测试），同一次运行里新插入的同名属性要放行，多个属性还要按源码顺序输出。