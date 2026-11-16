**档案：JsonWriter#value(double) 与 value(Number) 在 lenient 模式下行为不一致**

【1 题面要点】
- 要求的行为：在 lenient 模式下，`value(double)` 也应能写出 `NaN`、`Infinity`、`-Infinity`，与 `value(Number)` 一致，且不用装箱。
- 复现：给了装箱的变通写法 `out.value((Number) Double.valueOf(Double.NaN))`，没有给完整复现代码。
- 期望输出：没有给具体输出，只暗示 lenient 下应写出 `NaN` 之类的字面量。
- 修法建议：没有明确给出。隐含做法是让 `value(double)` 像 `value(Number)` 那样判断 `!lenient`。题面照抄的关键句是 `if (!lenient && (string.equals("-Infinity") ...` 和 `if (Double.isNaN(value) || Double.isInfinite(value)) { throw ...`。
- 理由：装箱性能较差。

【2 相关代码】
- `gson/src/main/java/com/google/gson/stream/JsonWriter.java:493-501`：`value(double)`。494 行无条件对 NaN 或无穷大抛 `IllegalArgumentException("Numeric values must be finite, but was ...")`。这是要改的主要位置。
- `JsonWriter.java:522-536`：`value(Number)`。529 行已经有 `!lenient &&` 判断，是参考实现。
- `JsonWriter.java:486-492` 和 `518-520`：两处 javadoc 写着“a finite value. May not be NaNs or infinities”，在 lenient 下已不准确。
- `JsonWriter.java:230-231`：类级 lenient 文档已写“Numbers may be NaNs or infinities”。
- `JsonWriter.java` 中 `lenient` 字段及 `isLenient()` 已存在。

【3 并列与牵连】
- `JsonTreeWriter.java:170-176`：`value(double)` 已经是 `!isLenient() && (...)` 才抛异常。它是现成的并列参照，不需要改。
- `JsonTreeWriter.java:183-197`：`value(Number)` 同样按 lenient 判断。
- `Gson.java:274-320`：`doubleAdapter` 和 `floatAdapter`。
  - 非 `serializeSpecialFloatingPointValues` 时，先调 `checkValidFloatingPoint`（322-328）抛异常，再调 `out.value(value)`，传的是 `Number`。
  - 开启 `serializeSpecialFloatingPointValues` 时使用 `TypeAdapters.DOUBLE`/`FLOAT`。
- `TypeAdapters.java` 中有大量 `out.value(...)` 调用，包括 DOUBLE、FLOAT 等。
  - 这些适配器多半传 `Number`，走 `value(Number)`，不受影响。
  - 若有传原始 `double` 的调用点，在 lenient 下行为会变，但 Gson 的写入器通常已把 lenient 设为 true。
  - 这一点需要核对：`Gson.newJsonWriter` 是否设 lenient，以及 `serializeSpecialFloatingPointValues` 的判断是否仍由 Gson 的适配器负责。我没有读到这部分。
- 没有 `value(float)` 重载，无需成对修改。

【4 现有测试与约定】
- `JsonWriterTest.java:174-193` `testNonFiniteDoubles`：非 lenient 下，`jsonWriter.value(Double.NaN)`、`NEGATIVE_INFINITY`、`POSITIVE_INFINITY` 都应 `fail()` 或抛 `IllegalArgumentException`。这个测试在默认非 lenient 下仍成立，与修改不冲突。
- `JsonWriterTest.java:195-214` `testNonFiniteBoxedDoubles`：对装箱的 `Double` 做同样断言，同样不冲突。
- 目前没有 lenient 下写 NaN 的测试。我只 grep 了 NaN/Infinity 相关词，没有确认 `JsonWriterTest` 里是否有其他 lenient 相关用例。
- 隐藏测试大概率是新增 lenient 版本的 `testNonFiniteDoubles` 和 `testNonFiniteBoxedDoubles`。它们会设置 `setLenient(true)`，断言输出形如 `[NaN,-Infinity,Infinity]`。
- 约定：`JsonTreeWriter` 的 lenient 写法，以及 `value(Number)` 的现有写法，都是仓库内的参考。与题面期望没有冲突。

【5 边界与隐含要求】
- 顺序：`value(Number)` 里先 `writeDeferredName()` 再检查、最后 `beforeValue()`。`value(double)` 目前是先检查再 `writeDeferredName()`。保持“非 lenient 时先抛异常，不留下已写入的名字”这个顺序更稳妥。
- 输出字面量：`Double.toString` 对 NaN、Infinity、-Infinity 分别给出 `NaN`、`Infinity`、`-Infinity`，与 `value(Number)` 一致，无需特殊处理。
- 异常信息和 javadoc 需要同步更新。
- lenient 下的 `-0.0` 等普通值不受影响。
- 非 lenient 行为必须保持不变（现有测试覆盖）。

【6 改动规模】
- 主要改 1 个文件、1 处：`JsonWriter.value(double)` 加 `!lenient &&`，约 1 行。
- 同文件再改 2 处 javadoc。
- 测试侧是新增用例。
- 属于局部修补，不涉及新增结构或跨层改动。

【7 难点一句话】
改动本身很小，主要风险在于有没有漏看 Gson 内部适配器对 lenient 下 `value(double)` 的依赖，以及要不要同步 javadoc。