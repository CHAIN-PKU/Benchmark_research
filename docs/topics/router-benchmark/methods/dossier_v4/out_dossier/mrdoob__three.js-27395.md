**档案：Sphere 缺少 `isSphere`**

**【1 题面要点】**
- 要求：`new Sphere().isSphere === true`，和 Box3 的 `isBox3` 对齐。
- 题面给了最小复现：`a = new Sphere(); if(a.isSphere){ debugger }`。动机是 `if(collider.isSphere)`。
- 没有期望输出或修法建议。关键句："Box3 has this.isBox3 = true; Sphere does not have this.isSphere;"。

**【2 相关代码】**
- `src/math/Sphere.js:8-15`：`class Sphere` 的 constructor 只设置了 `this.center`（行 12）和 `this.radius`（行 13）。要在 constructor 开头加 `this.isSphere = true;`。
- 参照写法：`src/math/Box3.js:7` 是 `this.isBox3 = true;`，`src/math/Plane.js:12` 是 `this.isPlane = true;`。两处都放在 constructor 最前面。

**【3 并列与牵连】**
- 并列实现：同类的 Ray、Frustum、Box2、Line3、Triangle 等也没有 `is*` 标志。我用 grep 查过，`isSphere`、`isBox3`、`isPlane`、`isRay`、`isFrustum` 里只有 Box3 和 Plane 有。题面只要求 Sphere，不需要顺带改其他类。
- 文档：`docs/api/{en,zh,it,ar}/math/Box3.html` 和 Plane.html 都有 `[property:Boolean isBox3]` 条目，写着 "Read-only flag to check if a given object is of type [name]."。Sphere.html 的 Properties 段（行 24 起）只有 `center` 和 `radius`。补文档是可选的，隐藏测试不会检查。
- 影响面：新增一个实例属性，不会改变其他行为。`src` 里没有地方用 `isSphere` 做分支。

**【4 现有测试与约定】**
- `test/unit/src/math/Box3.tests.js:53-61` 的 `isBox3` 测试：
  - `assert.ok( a.isBox3 === true )`
  - `const b = new Sphere(); assert.ok( ! b.isBox3 )`
- `test/unit/src/math/Plane.tests.js:54-63` 的 `isPlane` 测试结构相同，反例用 `new Vector3()`。
- `test/unit/src/math/Sphere.tests.js` 现在没有 `isSphere` 测试。文件头已经 import 了 Box3、Vector3、Sphere、Plane，所以隐藏测试很可能是照 Box3 的模式写：`new Sphere().isSphere === true`，且 `!new Box3().isSphere` 或 `!new Vector3().isSphere`。
- 与题面不冲突。约定一致，是 `this.isX = true` 放在 constructor 里，不放在原型上。

**【5 边界与隐含要求】**
- 其他类型不能有 `isSphere`。Box3 没有，所以不要写成在公共基类上设置。
- 必须在 constructor 里设置。`new Sphere( center, radius )` 带参数时也要有这个标志。
- `clone()` 和 `copy()` 返回的是 `new Sphere`，所以自动带标志，不用额外处理。
- 不要把标志放进 `toJSON` 或 `set`。

**【6 改动规模】**
- 必要改动：1 个文件，1 行（`src/math/Sphere.js`）。
- 顺带改动：`Sphere.tests.js` 加一个测试，各语言的 `Sphere.html` 加文档条目（共 4 个），这两项可选。
- 局部修补，不新增结构。

**【7 难点一句话】**
几乎没有难度：照抄 Box3 和 Plane 的写法，在 Sphere 的 constructor 里加一行 `this.isSphere = true;` 即可。唯一要留意的是放进 constructor，而不是原型或别处。