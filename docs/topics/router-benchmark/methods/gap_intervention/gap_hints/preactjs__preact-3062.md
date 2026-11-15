## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) src/diff/props.js setProperty 约110-122行：`name in dom` 分支 value==null 时执行 dom[name]=''，tabIndex 会被转成0，这是问题所在，同分支其他属性也会受影响，不要只处理 tabIndex。2) 该分支对 null/undefined 只赋值不走 removeAttribute，需核对131-140行兜底路径在此场景下是否会执行。3) diffProps 第18行删除 prop 时传 null 调用 setProperty，所以'prop 被移除'和'显式设为 undefined'都要覆盖。4) src/diff/index.js 约437/444行对 value/checked 的调用依赖现有置空为''的行为，改动时不能破坏。
B. tabIndex 为 undefined/null 时应移除属性；0 要保留（注意 ==null 与真假判断的差别）；-1 要保留；全小写 tabindex 写法；其他空值会被强制成默认值的属性（value、width、height、maxLength、rowSpan、colSpan）；先有值后变 undefined 要移除，之后再设值要恢复。
C. 124-129行注释中关于 false 与 ARIA 的约定不能改变；test/browser/ 下已有属性测试（如 render.test.js 中 value/checked 置空用例）要先搜索并跑一遍；test/browser/svg.test.js 用 spy 断言 removeAttribute，可参考；库对体积敏感，保持精简。
D. 1) 先渲染 tabIndex=0 或 1 再重渲染为 undefined，断言 hasAttribute('tabindex') 为 false。2) 重渲染为 null 与直接去掉该 prop，结果应一致。3) 跑 value、checked、input value、select 的清空相关现有测试，并验证 tabIndex=0 初始渲染后属性仍为 '0'。
