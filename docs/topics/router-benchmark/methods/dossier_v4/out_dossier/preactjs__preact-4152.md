**Preact「`{new String('hi')}` 渲染为空」仓库档案**

**【1 题面要点】**
- 要求的行为：`<div>{ new String('this should work') }</div>` 要渲染出文本。题面说 React 里这样写可以。
- 复现：只给了一个 colab 链接，里面是 React 和 Preact 的对比。题面正文里没有期望 HTML 输出，也没有修法建议。
- 动机：用户想给字符串挂元数据（`new String('thing').metadata = 123`），同时让 Preact 把它当字符串渲染。
- 可以推断的期望：`scratch.innerHTML` 等于该字符串的内容。

**【2 相关代码】**（均已读过）
- `src/diff/children.js:58-106`：`diffChildren` 里逐个归一化 child，是最可能要改的位置。
  - `:61-67`：`null`、`boolean`、`function` 变成 `null`。
  - `:71-83`：`typeof` 为 `string`、`number`、`bigint` 的 child 被包成 `createVNode(null, childVNode, null, null, childVNode)`，即文本 vnode，`props` 就是原始值。
  - `:84`：数组被包成 `Fragment`。
  - `:92`：用 `childVNode._depth > 0` 判断 vnode 是否被复用，需要克隆。
  - `:104-105`：其余情况直接当 vnode 使用。
- 根因推断：`new String('x')` 的 `typeof` 是 `'object'`，上面没有分支能接住它，于是落到 `:104` 的 else。这个 String 对象没有 `_depth`、`_parent` 等字段，又没有被 `createElement` 处理过，`constructor` 是 `String`。
- `src/diff/index.js:43`：`if (newVNode.constructor !== undefined) return null;`。这是防 JSON 注入的检查，String 对象的 `constructor === String`，所以 `diff` 直接返回 null，什么都不渲染。这就是「空白」的直接原因。
- `src/diff/index.js:337-404`：`diffElementNodes` 的文本节点路径。
  - `:378`：`document.createTextNode(newProps)`，传入 String 对象时会被强制转成字符串。
  - `:403-404`：`oldProps !== newProps` 时执行 `dom.data = newProps`。
- `src/create-element.js:55-82`：`createVNode`，vnode 的 `constructor` 固定为 `undefined`。
- `src/create-element.js:97-98`：`isValidElement` 用 `constructor === undefined` 判断。
- `src/diff/children.js:291-302`：`toChildArray` 把非 null、非 boolean 的值原样推入，不做字符串归一化。

**【3 并列与牵连】**
- 并列实现：`children.js:72-75` 的 `typeof` 三连是唯一的文本 vnode 创建点，不需要多处同步。
- `src/diff/index.js:56` 之后的组件路径：组件返回 `new String(..)` 时，渲染结果也会经过 `diffChildren`，应该会一起被修好。这一点我没有核实。
- 根节点 `render(new String('x'), root)`：`src/render.js` 会把它包进 `createElement(Fragment, ...)`，也会进入 `diffChildren`，应该同样被覆盖。我没有读 `render.js`。
- 文本更新：`index.js:403` 用 `oldProps !== newProps` 比较。如果 props 存的是 String 对象，每次渲染引用都不同，会重复写 `dom.data`。如果归一化时转成原始字符串，就不会有这个问题。
- `toChildArray`（`:291`）及其使用方 `compat/src/Children.js:5,13,16`、`suspense-list.js:90`、`render.js:185,193`：对 String 对象不做处理。是否要同步改，取决于修法的范围。
- `debug/src/debug.js:530` 附近有关于对象 `toString` 的处理，涉及 debug 的无效对象检查。我只在 grep 里看到这一行，没有读上下文，可能需要核对 debug 是否会对 String 对象报错。
- `findMatchingIndex`（`:321-359`）：通过 `key` 和 `type` 匹配。文本 vnode 的 `type` 都是 `null`，不受影响。

**【4 现有测试与约定】**
- `test/browser/render.test.js:272-296`：
  - `render(0, scratch)` 之后 `expect(scratch.innerHTML).to.equal('0')`。
  - `render(BigInt(4), scratch)` 之后断言 `'4'`。
  - `render('Testing, huh! ...', scratch)` 之后断言原字符串。
  - 没有 String 对象的测试，也没有对象型 child 的测试。
  - 隐藏测试大概率是在这里或 `children` 相关测试里新增一条类似断言。
- `test/browser/components.test.js:514-536` 有 `should render string`、`should render number as string`、`should render null as empty string`，是组件返回值的相关约定。
- 约定：`index.js:43` 的注释说明了 `constructor !== undefined` 检查是为了防 JSON 注入。修复不能把它放宽，否则会让任意带 `constructor` 的对象被当作 vnode。
- 外部规范：React 对 String 对象的行为是渲染其字符串内容。与题面一致，没有冲突。

**【5 边界与隐含要求】**
- 其他包装类型：`new Number(1)`、`new Boolean(...)`。题面只提 String，Boolean 对象的 `typeof` 也是 `'object'`，是否一并处理不确定。
- `String` 子类，或带元数据的 String 对象：用户场景是 `thing.metadata = 123`，渲染时只用字符串值。
- 空字符串对象 `new String('')`：应渲染成空文本节点，与现有 `render.test.js:68` 的行为一致。
- 重新渲染和更新：先 `new String('a')`，再 `new String('b')`，或同一对象再次渲染，`dom.data` 要正确更新。
- 同一个 String 对象被复用（`{s}{s}`）：每次要生成独立的文本 vnode，不能共用同一个 vnode。
- 水合（hydration）：文本节点路径在 `index.js:402-405`，转成原始字符串后应与现有行为一致。
- 不能破坏 `createElement` 之外的 vnode 判断：`constructor === String` 的判断要放在 `_depth` 等分支之前，才不会被克隆路径或 `:104` 的 else 拦住。

**【6 改动规模】**
- 核心改动：只涉及 `src/diff/children.js:71-83` 附近，预计 1 个文件、1 到 2 处。做法是让 String 对象也走文本 vnode 分支，并把值转成原始字符串，或者放进 props 再转换。
- 测试：在 `test/browser/render.test.js` 加断言。
- 体积：Preact 对包体积很敏感（有 size 检查），所以改动要尽量短。

**【7 难点一句话】**
- 难点不在定位，根因很清楚：`typeof` 为 `'object'` 的 String 对象落入 else 分支，随后被 `diff` 的 `constructor !== undefined` 检查丢弃。
- 真正的难处是怎样判断「这是 String 对象」。要在不放松 JSON 注入防护、不影响普通 vnode 判断、不增加太多字节的前提下写出判断条件。同时还要决定是否把 `Number`、`Boolean` 等其他包装对象一并处理。