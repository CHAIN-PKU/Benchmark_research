## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

A. 1) javac HandleExtensionMethod.getExtension (约L120) 的修饰符过滤:String.class 的 public 实例方法如 startsWith(String,int) 为何被当作候选,需核对过滤语义。2) eclipse/handlers/HandleExtensionMethod.java 是并列实现,需检查是否有同样问题并一起处理。3) handleMethodCall 中名称匹配、首参可赋值、改写的流程,以及 suppressBaseMethods 与 L178 提前返回,确认修复后不会误改写合法调用。
B. 1) 提供者含 public static 方法且与接收者实例方法同名时,原功能不变。2) 提供者含 public 非静态方法或非 public 静态方法,都不应成为扩展方法。3) String.class 与自定义空提供者混用、多个提供者并存。
C. 1) 现有测试在 test/transform/resource/before/ExtensionMethod*.java,期望在 after-delombok/、after-ecj/,另有 messages-* 目录,新增用例按此结构,javac 与 ecj 两边都要对。2) experimental/ExtensionMethod.java 的 javadoc 对扩展方法的定义(public static),以此核对。
D. 1) 题面最小例子能编译且 startsWith 不被改写。2) 跑全部 ExtensionMethod* 变换测试(javac+ecj),重点 Plain/Suppress/Names。3) 新增测试:提供者同时含同名的 public 非静态与 public static 方法,只有静态方法参与改写。
