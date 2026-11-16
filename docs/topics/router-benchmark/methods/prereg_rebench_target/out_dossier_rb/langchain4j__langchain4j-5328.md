**档案：@Tool 方法未从父类继承**

仓库快照是只读的，我没有运行任何代码。以下都是读源码和 grep 得到的结论。

**【1 题面要点】**
- 要求的行为：工具类的父类里带 `@Tool` 的方法，也要被识别为工具并能被调用。
- 症状是 LLM 说“不知道该调用哪个工具”，也就是父类方法没有生成 ToolSpecification。
- 题面没有给复现代码、期望输出或修法建议。
- 题面有一句 “This should be done in LC4J too if it already doesn't work there.”。这句话指向 LC4J，但“LC4J”在这里指什么，题面没说。
- 题面的 Interface 一节写着 “No new interfaces are introduced.”，所以不新增公共 API。

**【2 相关代码】**
- `langchain4j/.../service/tool/ToolService.java:229`，`findTools(Object)`：这是 AI Service 注册工具对象的主路径。
  - 它遍历 `objectWithTools.getClass().getDeclaredMethods()`，而 `getDeclaredMethods()` 不含父类方法，这是根因之一。
  - 随后用 `getAnnotatedMethod(method, Tool.class)` 判断是否带注解。
  - 通过后调用 `validateToolParameters`，用 `toolSpecificationFrom` 生成规格，再用 `createToolExecutor` 建执行器。
  - 一个方法也没找到时抛 `illegalConfiguration("Object '%s' does not have any methods annotated with @Tool")`。
  - 如果子类自己没有 `@Tool` 方法、全部在父类里，现状下会直接抛这个异常。
- `langchain4j-core/.../agent/tool/ToolSpecifications.java:62`，`toolSpecificationsFrom(Class)`：同样使用 `getDeclaredMethods()` 加 `isAnnotationPresent(Tool.class)`，然后调用 `validateSpecifications` 检查重名。
  - `:78` 的 `toolSpecificationsFrom(Object)` 直接委托给上面的 Class 版本。
- `langchain4j/.../service/tool/DefaultToolExecutor.java:68-80`，`findMethod`：按名称在 `getDeclaredMethods()` 里找方法，用于构造器 `DefaultToolExecutor(Object, ToolExecutionRequest)`。
  - 它同样看不到父类方法，而且只按名字匹配、不看注解。
- `langchain4j-core/.../internal/Utils.java:535`，`getAnnotatedMethod`：只检查方法自身，或者 JDK 代理类所实现接口上的同名方法，不处理类继承。

**【3 并列与牵连】**
- 并列的三处 `getDeclaredMethods()` 实现（ToolService、ToolSpecifications、DefaultToolExecutor.findMethod）需要同步改，否则会出现“有规格却找不到方法”的错位。
- 题面提到的 “LC4J” 很可能就是 `ToolSpecifications`（core 模块）这一处。
- 调用点：
  - `ToolService.tools(Collection<Object>)` 在 `ToolService.java:126` 调用 `findTools`。
  - `langchain4j-skills/.../AbstractSkill.java:163` 调用 `ToolService.findTools`。
  - `toolSpecificationsFrom` 的使用者在测试和 IT 里（见第 4 节），没有在 src/main 里看到别的调用者。
- `langchain4j-agentic` 里还有一批 `getMethods()`/`getDeclaredMethods()`，如 `AgenticServices.java:741` 和 `AgentUtil.java:139/157/313`。这些处理的是 `@Agent` 等注解，不是 `@Tool`，大概率不用改，但也可能相关，我没有逐个核对。
- 改了扫描方式后，父类和子类的重名方法（override）、静态方法、桥接方法、私有方法都可能被扫进来。

**【4 现有测试与约定】**
- 测试位置：
  - `langchain4j-core/src/test/.../agent/tool/ToolSpecificationsTest.java`，有 4 处使用 `toolSpecificationsFrom`。
  - `langchain4j-google-ai-gemini/.../FunctionMapperTest.java`，有 2 处。
  - `langchain4j/src/test/.../AbstractAiServiceIT.java`，有 2 处。
  - 我没有逐行读取 ToolService 和 DefaultToolExecutor 的具体断言，所以不能引用断言原文。
- `UtilsTest.java:463-481` 测试 `getAnnotatedMethod`：
  - `:463` 是 `assertThat(getAnnotatedMethod(myMethod, MyAnnotation.class)).contains(myMethod)`。
  - `:464` 对其他注解断言 `isEmpty()`。
  - `:480` 测代理类场景，返回接口上的方法。
  - 隐藏测试可能在这里加类继承用例，也可能改动这个函数的签名或语义。
- 我没有找到现成的“继承工具”的参考实现或规范。外部可参考的是 Java 反射惯例：遍历 `getSuperclass()` 链，或同时用 `getMethods()` 与 `getDeclaredMethods()`。
- 与题面不冲突，现有测试只覆盖“自身声明方法”。

**【5 边界与隐含要求】**
- 多层继承（祖父类）。
- 子类覆写父类 `@Tool` 方法：
  - 去重，不能因为重名触发 `validateSpecifications` 的 “Tool names must be unique”。
  - 覆写方法上没有 `@Tool` 时，是否仍视为工具？按 Java 注解不继承的规则，需要沿父类方法查注解。
  - 子类重新标注时，以子类为准。
- 父类方法是 `private`、`protected` 或包私有：调用靠 `setAccessible` 的回退（`DefaultToolExecutor.java:107`），应该能工作。
- 父类是非 public 类时，反射调用的访问性。
- 排除 `Object` 以及 JDK 类，避免扫到不相关的方法。
- 泛型父类带来的桥接方法和合成方法，可能产生重复的规格。
- 代理（Spring AOP、CGLIB）：对象的 class 是代理子类，而 `getAnnotatedMethod` 现有逻辑只处理 JDK 接口代理。
- 若 `DefaultToolExecutor.findMethod` 不改，用 `ToolExecutionRequest` 构造的执行器查不到父类方法。
- 确定性顺序：`getDeclaredMethods()` 本身不保证顺序，隐藏测试若断言列表顺序，需要稳定。

**【6 改动规模】**
- 大约 2 到 3 个主文件：`ToolService.findTools`、`ToolSpecifications.toolSpecificationsFrom`，以及可选的 `DefaultToolExecutor.findMethod`。
- 每个文件改 1 处，必要时在 `Utils` 里加一个“收集类层级方法”的辅助函数。
- 属于局部修补，不涉及新增公共接口，也不贯穿多层。
- 另需补测试。

**【7 难点一句话】**
改动本身不大，难点在于：除了扫描方式，还要决定覆写、桥接方法和重名怎么去重，并且让 ToolService、ToolSpecifications 和 DefaultToolExecutor 三处行为一致。