# 细粒度归因格式（训练集与留出集共用，保证同一口径）

对每道挂题输出一个 JSON 行（jsonl），字段：
- task
- env_suspect: true/false（测试没加载、缺依赖、超时、评测环境问题 → true，这类不算 DS 能力）
- coarse: 粗类，五选一：HIDDEN（测试要的行为题面没写/与题面不一致）、NARROW（题面只举一例，需更通用修法；或反过来 DS 泛化过头、应更窄）、SIBLING（兄弟/并列实现漏改）、WRONG_LOC（改错地方/没找到真正根因）、OTHER
- mechanism: 一句话（≤30 字）写清「DS 具体错在哪」，要具体到行为，例如「heredoc 只含空白的行被当空行吞掉 tab」「协议相对 URL 应拼到 baseURL 而不是报错」
- behavior_domain: 从下面选 1~2 个最贴切的（不够再自造，写 NEW:xxx）：
  error_message（精确报错/提示文案）, null_empty（空值/缺省/零值）, default_semantics（默认值/默认行为）, datetime_format（日期时间/时区/格式解析）, string_format（格式化/unicode/空白/转义）, serialization（序列化/JSON/编码）, type_schema（类型/schema/校验）, recursion_nested（递归/嵌套/深层结构）, multi_entry（多入口/多个调用点/并行路径）, platform_version（平台/版本差异）, spec_compat（对齐外部规范或参考实现如 GNU/RFC）, state_side_effect（状态/副作用/顺序）, api_shape（新增 API 的形状/参数/返回值）, config_option（配置项/选项解析）, perf_resource（性能/资源）
- failing_tests: 挂的测试名（原样，最多 4 个）
- prerun_signal: 动手前从「题面 + 基线仓库」能看到的线索（≤40 字）；看不到写「无」
- signal_where: issue / repo_tests / repo_docs / repo_code / none
- confidence: high/med/low

依据：题面、两次 DS 补丁、两次挂的测试与报错、标准答案（标准答案只用于事后归因）。两次挂法不同就以更典型的一次为主，在 mechanism 里注明。不要使用对上游的记忆，以材料为准。
