## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) Object3D 无 material，真正的赋值在 Mesh.js:68、Line.js:37、Points.js:35、Sprite.js:146 的 copy()，需逐个核对。2) LineLoop/LineSegments/SkinnedMesh/InstancedMesh 继承 super.copy，确认没有单独覆盖。3) Sprite 的 material 是单对象，判断是否需要改、是否保持写法一致。4) 搜 src 和 examples/jsm 中 .material = source.material / this.material 的并列实现，InstancedMesh.js:138 的 _mesh 临时赋值是 raycast 用的，不要误改。
B. 1) material 为单对象时克隆后仍应是同一引用。2) 数组时应为新数组，元素仍是同一批材质。3) 空数组或 undefined。4) 修改克隆后的数组不应影响原对象。
C. 1) 参照 Mesh.copy 对 morphTargetDictionary 与 InstancedMesh.copy 对 instanceColor 的拷贝容器写法。2) 查 test/unit/src/objects 下 copy/clone 测试是否有占位或需补充。3) 核对 Object3D.toJSON 约 828-832 行与 ObjectLoader 对数组 material 的序列化约定。4) 查 docs 中 .material 与 clone 的说明。
D. 1) Mesh 传入 [m1,m2] 后 clone，检查 clone.material !== mesh.material 且元素同一引用。2) Line/LineSegments/Points 同样检查，单 material 的 Mesh 和 Sprite 检查引用不变。3) InstancedMesh/SkinnedMesh 的 clone 做数组 material 检查，并跑 objects 相关单测。
