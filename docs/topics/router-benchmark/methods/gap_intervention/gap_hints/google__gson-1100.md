## 动手前请注意（审查者给的提醒清单，只是提醒，不是答案）

**A. 题面没点名、但可能也要处理的位置**
1. `gson/src/main/java/com/google/gson/DefaultDateTypeAdapter.java` 的 `read(JsonReader)`：开头 `in.peek() != STRING` 就抛 `JsonParseException`。JSON 里是 `null` 时反序列化大概率也会失败，所以别只看 `write`。
2. 同包的并列实现可以对照，看它们怎么处理 null：`internal/bind/DateTypeAdapter.java`（`write` 里有 null 判断）、`internal/bind/SqlDateTypeAdapter.java`、`extras/.../UtcDateTypeAdapter.java`。
3. `GsonBuilder` 里 `setDateFormat` 的几个重载（pattern、style 和 style 加 `Class`）都会创建 `DefaultDateTypeAdapter`。请核对这些路径是否都经过同一个 `write` 和 `read`，以及 `Date`、`java.sql.Date`、`Timestamp` 三种 dateType 是否都会受影响。

**B. 可能被检查的输入/边界**
1. 顶层直接序列化 null，例如 `gson.toJson((Date) null)`，以及 `toJson(null, Date.class)`。这时 `Gson` 对 null 的处理路径和 POJO 字段不同。
2. 开启 `serializeNulls()` 与不开启时的输出不同，字段值为 null 时要核对 JSON 里是 `"age":null` 还是整个字段被省略。
3. 集合或 Map 中含 null 元素。如果用 `java.sql.Date` 或 `Timestamp` 作为 dateType，也要核对。
4. 反序列化 `{"age":null}` 时，结果应该是字段为 null，而不是抛异常。

**C. 仓库已有约定**
1. `DateTypeAdapter.write` 的约定：`value == null` 时调用 `out.nullValue()` 然后 `return`。你的实现应与它一致，输出形式也保持一致。
2. `DefaultDateTypeAdapterTest.java` 里目前没有任何 null 相关用例。看看它现有测试的风格（直接构造适配器、用 `StringWriter` 或 `gson.toJson`），然后按同样风格补测试。
3. `write` 里有 `synchronized (localFormat)`（issue 162 的线程安全约定）。改动时不要破坏它，也不要让 null 判断改变加锁行为。

**D. 提交前建议自测**
1. 题面的例子：POJO 的 Date 字段为 null，配合 `setDateFormat("yyyy-MM-dd")` 做 `toJson`，不抛异常，并检查输出文本。
2. 往返测试：`{"age":null}` 经 `fromJson` 得到 null 字段。同时也测非 null 日期，确认原有格式化和解析行为没变。
3. 用 `setDateFormat(int style)` 这类 style 重载，以及 `serializeNulls()` 开和关，各跑一遍 null 字段。最后跑 `DefaultDateTypeAdapterTest` 和 `DateTypeAdapter` 相关的现有测试。
