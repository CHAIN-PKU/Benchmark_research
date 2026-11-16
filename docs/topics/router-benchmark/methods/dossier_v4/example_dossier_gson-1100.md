**Gson #1100 档案：`setDateFormat` 下 null 日期字段 toJson 抛 NPE**

**【1 题面要点】**
- 期望行为：`new GsonBuilder().setDateFormat("yyyy-MM-dd").create().toJson(p)`，其中 `Person.age`（`Date`）为 null，不应抛 NPE。题面没有写期望输出。按 Gson 默认惯例，应是字段被省略，即 `{}`。开启 `serializeNulls` 时是 `{"age":null}`。
- 题面给了复现：POJO 加 `GsonBuilder().setDateFormat(...)`。也给了完整栈。
- 栈顶是 `DefaultDateTypeAdapter.write(DefaultDateTypeAdapter.java:88)` 调 `DateFormat.format(null)`，随后在 `Calendar.setTime` 抛 NPE。
- 题面没有给修法建议。

**【2 相关代码】**（路径均在 `gson/src/main/java/com/google/gson/` 下）
- `DefaultDateTypeAdapter.java:86-91` 的 `write(JsonWriter, Date)` 是根因。它没有判 null，直接执行 `enUsFormat.format(value)`，并包在 `synchronized (localFormat)` 里。
- `DefaultDateTypeAdapter.java:94-109` 的 `read`：
  - 开头 `in.peek() != JsonToken.STRING` 就抛 `JsonParseException("The date should be a string value")`，所以 JSON 的 `null` 读入同样会失败。
  - 这是与 write 对称的 bug，题面没提。
- `GsonBuilder.java:579-603` 的 `addTypeAdaptersForDate`：
  - 设置了 pattern 或 style 后，把 `DefaultDateTypeAdapter` 注册给 `Date`、`Timestamp`、`java.sql.Date` 三个类型。
  - 这个适配器 `final` 且包可见，只在这里实例化。

**【3 并列与牵连】**
- 同一个适配器类实例分别用于 Date、Timestamp、sql.Date，所以改它的 `write` 和 `read` 就能覆盖这三种类型。
- 并列的内置实现已经处理了 null，可作参照：
  - `internal/bind/DateTypeAdapter.java:54-58` 的 `read` 先判 `JsonToken.NULL` 再 `nextNull()` 返回 null。
  - 同文件 `:78-82` 的 `write` 在 value 为 null 时调 `out.nullValue()`。
  - `SqlDateTypeAdapter.java:51-54` 和 `:65` 也做了同样处理。
  - `TimeTypeAdapter.java:50` 和 `:63-64` 同理。
- 备选方案是在 `GsonBuilder` 中对适配器调用 `.nullSafe()`。`TypeAdapter.java` 里有 `nullSafe()`，文档在 `:77-90`。
- 这个类里的 `toString()` 和构造器不需要改。

**【4 现有测试与约定】**
- `DefaultDateTypeAdapterTest.java` 的测试都是格式化和解析，例如 `:48` 的 `assertFormatted("Jan 1, 1970 12:00:00 AM", new DefaultDateTypeAdapter(Date.class))`。我的 grep 没发现任何 null 相关测试。
- `functional/DefaultTypeAdaptersTest.java:456-547` 覆盖 `setDateFormat` 的序列化。例如 `:461` 的 `assertEquals("\"2011-09-11\"", json)`，`:505` 的 `"[\"1970-01-01\"]"`，`:523` 和 `:541` 也是类似断言。这些都没有 null 用例。
- 约定：`TypeAdapter` 的文档（`TypeAdapter.java:77` 起）要求适配器自己处理 null，或使用 `nullSafe()`。
- 与题面期望没有冲突。

**【5 边界与隐含要求】**
- 顶层 `toJson((Date) null)`，以及 `List<Date>` 中含 null 元素。
- `serializeNulls` 开启与否：关闭时字段应被省略，开启时输出 `null`。这一点由 `out.nullValue()` 与 writer 配合完成，具体行为我没有逐层核对，建议确认。
- 反序列化 `{"age":null}` 应得到 null 字段，对三种类型都成立。
- 三种类型（Date、Timestamp、sql.Date）各自的 null 行为都应一致。
- `read` 中 null 判断要放在 STRING 检查之前，否则仍会抛 `JsonParseException`。
- 隐藏测试可能同时断言 write 和 read 的 null，也可能只测 write。

**【6 改动规模】**
- 只涉及 1 个源文件，即 `DefaultDateTypeAdapter.java`，改 2 个方法（write 和 read），每处约 3-4 行。
- 另有可选的测试文件（`DefaultDateTypeAdapterTest` 或 `DefaultTypeAdaptersTest`）。
- 局部修补，不需要新结构。

**【7 难点一句话】**
- 修法本身直观，难点只在别漏掉与 write 对称的 `read` 的 null 分支，并让三种日期类型的 null 行为一致。