# 仓库档案：Object3D.clone() 时克隆 material 数组

## 【1 题面要点】
- 要求的行为：`clone()` / `copy()` 之后，如果 `material` 是数组，副本应持有一个新数组，不再和源对象共用同一个数组引用。数组里的各个 material 仍然共享引用，不克隆 material 本身。
- 复现和期望输出：题面没有给。
- 修法建议（原文）："Cloning the materials array when `clone()` is called seems like it wouldn't change too much performance wise."
- 约束（原文）："as long as the materials themselves are not cloned, things should be fine"。
- 题面写的是 `Object3D.clone()`，但 `Object3D` 本身没有 `material`。真正要改的是各带 material 的子类。

## 【2 相关代码】
以下各处目前都是 `this.material = source.material;`，也就是直接共用引用：
- `src/objects/Mesh.js:52-73`：`copy()`，赋值在第 68 行。第 56-66 行已有 `morphTargetInfluences.slice()` 和 `Object.assign({}, morphTargetDictionary)`，可作写法参考。
- `src/objects/Line.js:33-42`：`copy()`，赋值在第 37 行。
- `src/objects/Points.js:31-40`：`copy()`，赋值在第 35 行。
- `src/objects/Sprite.js:140-150`：`copy()`，赋值在第 146 行。Sprite 的 material 一般是单个 `SpriteMaterial`。
- `src/core/Object3D.js` 的 `clone()` 是 `new this.constructor().copy(this)`，没有 material 相关逻辑。

## 【3 并列与牵连】
- 四个并列实现（Mesh、Line、Points、Sprite）各自独立赋值，没有共用的基类逻辑。只改 Mesh 会漏掉其余三个。
- 子类 `SkinnedMesh`、`InstancedMesh`、`LineSegments`、`LineLoop` 都通过 `super.copy` 继承，不用单独改。`SkinnedMesh.js:89` 和 `InstancedMesh.js:103` 调用的是 Mesh 的 `copy()`。
- `LOD.js:31` 的 `copy` 不涉及 material。
- 其他代码对 material 数组的处理（`Mesh.js:215` 和 `:273` 的 raycast、`WebGLRenderer.js:973` 和 `:1263`、`WebGLShadowMap.js:345`）都是只读遍历，不受影响。
- `Object3D.js:818` 是 `toJSON` 里处理数组 material 的地方，只读，不受影响。
- 仓库里没有 `Batched*` 对象。
- `examples/` 或 loader 里若有依赖共用数组引用的代码，我没有查，属于未查证项。

## 【4 现有测试与约定】
- 现有测试几乎不覆盖这个行为。`test/unit/src/objects/Mesh.tests.js:70` 是 `QUnit.todo( 'copy', ...)`。
- `Mesh.tests.js:53`、`Line.tests.js:47`、`Points.tests.js:46`、`Sprite.tests.js:46` 的 `material` 也都是 `QUnit.todo`。
- `Object3D.tests.js` 里没有 material 相关内容，`test/unit` 下也没有断言数组 material 的用例。
- 仓库里没有 material 数组克隆的参考实现。可对照的约定是 `Mesh.copy` 里对 `morphTargetInfluences` 用 `.slice()`，以及 `Material.copy`（`Material.js:415`）对数组类字段的处理。我没有读完 `Material.copy` 的后半部分，所以不确定它是否对 `clippingPlanes` 做了 slice。
- 与题面期望没有冲突，因为现有测试没有断言“共用同一数组引用”。
- 隐藏测试大概率会这样写：给 Mesh（也可能给 Line、Points）传数组 material，`clone()` 后断言 `clone.material !== source.material`，同时 `clone.material[0] === source.material[0]`。

## 【5 边界与隐含要求】
- 单个 material 要保持共享引用，不能对它调用 `.slice()` 或 `.clone()`。需要先用 `Array.isArray(source.material)` 判断。
- 数组里的元素不能克隆，要保持同一引用。
- `source.material` 为 `undefined` 时（`InstancedMesh.js:140` 有对 undefined 的判断）不能抛错。
- 空数组要能正常复制。
- 数组的 `slice()` 只是浅拷贝，这正是想要的行为。
- 几个类的 `copy()` 都要处理，包括 Line 和 Points，不止 Mesh。
- 递归克隆 children 时，每个子对象通过各自的 `copy()` 走同一路径，不需要额外处理。

## 【6 改动规模】
- 改 4 个文件（Mesh、Line、Points、Sprite），每处 1 行换成 3-5 行的判断。
- 局部修补，不新增结构，不贯穿多层。
- 另外可能补单元测试。

## 【7 难点一句话】
改动本身很简单。主要风险是漏掉 Line、Points、Sprite 这些并列的 `copy()`，或者把单个 material 误当成数组处理，破坏它的共享引用。