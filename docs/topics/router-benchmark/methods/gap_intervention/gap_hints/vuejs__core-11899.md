## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) pluginScoped.ts 第234–248行只处理父规则下直接的 decl 并检查子 rule，不处理 atrule 子节点里的直接声明；2) 题面说 @container/@supports/@layer 等任何 @ 规则都可能中招，不要只处理 @media；@keyframes 在 processRule 里有单独跳过逻辑，atrule 还可能嵌套；3) 第247行 shouldInject = deep 会影响含 atrule 子节点的父规则，改动时需核对。
B. 1) 父规则同时有直接声明、嵌套 .bar 规则和 @media（题面场景）；2) 父规则只有 @media 没有嵌套 rule 时输出应保持原样；3) @media 内既有声明又有嵌套规则、@media 套 @media、@supports 套 @media，声明与 @media 的混排顺序；4) :deep/:global/:slotted/:is/:where 父规则下的 @media。
C. 1) compileStyle.spec.ts 第44行 nesting selector 测试给出了「声明包进 & 并注入 id」的输出格式，新行为要与之一致；2) 同文件第217、226行 @media/@supports 测试是顶层 atrule 既有行为，不能回归；3) :deep 测试（约第104行）中 deep 父规则下不包 &。
D. 1) 题面完整例子，检查 @media 内声明带上 id 选择器；2) 用 @container/@supports 重复一遍，再测 @media 嵌套 @media；3) :deep 父规则下带 @media 的情形不应多包 & 或注入 id，并跑完整个 compileStyle.spec.ts。
