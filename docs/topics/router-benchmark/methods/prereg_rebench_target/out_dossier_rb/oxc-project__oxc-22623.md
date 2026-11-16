# 仓库档案：no-unused-vars 参数装饰器与同名参数属性

## 【1 题面要点】
- 要求的行为：构造器参数的装饰器表达式（如 `@Inject(foo.KEY) private readonly foo`）里的 `foo`，应解析到外层绑定（import 或 `const`），不能解析到同名的参数本身。外层 `foo` 因此算作已使用，不再报 no-unused-vars。
- 复现：
  ```ts
  const foo = { KEY: 'token' };
  declare function Inject(token: unknown): ParameterDecorator;
  export class C { constructor(@Inject(foo.KEY) private readonly foo: number) {} }
  ```
- 期望：无诊断。题面原话："Parameter decorators are evaluated at class-decoration time in the enclosing class scope, before any parameter binding exists in the parameter scope."
- 题面没有给修法建议，也没有指定改哪一层。"No new interfaces" 说明是行为修复。
- 题面提到的 #20670（类型参数被函数参数遮蔽）是同族 bug，但不在本题范围内。

## 【2 相关代码】
根因在 oxc_semantic，不在 linter 规则本身。
- `crates/oxc_semantic/src/builder.rs:2358` `visit_formal_parameter`：先 `param.bind(self)`，再在 2363 行 `visit_decorators(&param.decorators)`。此时 current_scope 已是函数作用域。
- `builder.rs:2374` `visit_formal_parameter_rest`：同样的结构，装饰器在 2379 行访问。
- `builder.rs:2642` `reference_identifier`：用 `self.current_scope_id` 创建 `Reference`，所以装饰器里的引用记在函数作用域上。
- `builder.rs:1838` `visit_function`：在 1864 行 `enter_scope`，在 1893–1917 行访问参数后调用 `resolve_references_for_current_scope`（627 行）。
- `builder.rs:627` 和 `557` `walk_up_resolve_reference`：从 `reference.scope_id()` 向上找绑定。装饰器引用的 scope 是函数作用域，所以先命中同名参数 `foo`，外层 `foo` 就成了未使用。
- `builder.rs:1978–2009`：箭头函数有同样的参数解析流程。
- `builder.rs:791` `visit_class`，799 行访问类装饰器：类装饰器当前是在类外层作用域访问的。

## 【3 并列与牵连】
- `visit_formal_parameter` 和 `visit_formal_parameter_rest` 是成对实现，都要处理。
- 参数装饰器只合法出现在 class 的构造器和方法里。方法也是 `visit_function`，且 TS 的 `declare`/overload 也走这条路。
- 改语义层会影响所有使用 oxc_semantic 的下游，例如 linter 里别的规则、transformer 的装饰器转换、isolated declarations。这些要靠 scope 和 reference 的 id 一致性。
- 装饰器里的引用 scope 改变后，语义快照（`crates/oxc_semantic/tests/fixtures/**/*.snap`）里的 reference 关联和 `node_id` 可能随之变化。
- no_unused_vars 目录里没有看到装饰器专用逻辑，grep 只命中测试文件。

## 【4 现有测试与约定】
- `oxc_semantic/tests/fixtures/typescript-eslint/decorators/parameter-property.ts` 和 `parameter.ts`，用的装饰器是顶层函数 `decorator`，不与参数同名。快照里 `decorator` 的 reference 直接挂在 Program 的符号上，没有同名冲突场景。
- linter 测试 `no_unused_vars/tests/typescript_eslint.rs:66-77`：`@ConstructorParameterDecoratorFactory(APP_CONFIG) config: AppConfig` 在 pass 用例里。第 80–88 行是 `@ConstructorParameterDecorator bar`，也是 pass。这些都不涉及同名遮蔽。
- 约定与规范：题面把行为参照放在 `@typescript-eslint/parser` 的 scope analyser。TS 规范里装饰器在参数作用域之外求值。与题面期望不冲突。
- 隐藏测试很可能是 `no_unused_vars` 的 pass 用例（题面复现），也可能附带 semantic 层断言或新增快照。我没有核实具体形式。

## 【5 边界与隐含要求】
- 解构参数，如 `@D foo`、`@D {foo}`：装饰器同样不应看到参数绑定。
- 函数声明、方法、构造器、箭头函数（箭头函数不允许装饰器），以及 `FormalParameterRest`（`...rest`）。
- 参数初始值 `= foo` 仍然应该看到参数绑定。只有装饰器要改，不能误伤 initializer 和类型注解。
- 装饰器里出现的类型引用或 `typeof foo` 同样要处理。
- 装饰器里含箭头函数或 class 表达式时，嵌套 scope 的父链要正确。
- 引用在 `resolve_references_for_current_scope` 之前被 checkpoint 机制批量解析，装饰器引用不能被当成函数作用域内的引用而被提前吞掉。
- 参数属性（`private readonly foo`）同时是参数绑定和类字段语义，不要改变参数本身的符号标志。
- 类名同名的情况：装饰器里引用类名时，类自身的绑定可见性不能被破坏。

## 【6 改动规模】
- 预估改 1 个源文件（`builder.rs`）里的 2 处，外加测试或快照。
- 局部修补：思路是让参数装饰器的引用绑定到函数作用域的父作用域，也就是临时把 `current_scope_id` 设为父 scope，或在 `Reference` 上设置父 scope。
- 难点在于要保持 `unresolved_references` checkpoint 和 `scope_id` 的一致。如果实现时需要新增状态，规模会略大。
- `visit_decorators` 在 `visit_formal_parameter` 里的位置（`param.bind` 之后）也要留意节点创建顺序，避免影响 AST 节点 id 和快照。

## 【7 难点一句话】
难点在于想清楚"装饰器引用该记在哪个 scope、何时解析"：当前 `reference_identifier` 取 `current_scope_id`（已是函数作用域），而 `resolve_references_for_current_scope` 又在参数访问后统一解析。既要让装饰器跳过参数绑定，又不能破坏参数初始值和类型注解的解析，也不能让节点 id 和 scope 嵌套关系变化，导致已有快照大面积改动。