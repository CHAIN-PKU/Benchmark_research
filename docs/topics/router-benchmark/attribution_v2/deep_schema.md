# 深度归因格式 v2（三层，每层都要证据）

每道挂题输出一行 JSON（jsonl），字段：
- task, run_attributed（1/2/both）
- L1_what（错在哪）：
  - failing_tests：挂的测试原名（从 run*_summary.json / test_output 原样复制，最多 5 个）
  - diff_vs_gold：DS 补丁与标准答案的逐处差异，列 1~4 条，每条「标准答案改了 文件:函数 做了X；DS 没改/改成了Y」
  - mechanism：一句话具体机制（≤40 字）
  - coarse：HIDDEN / NARROW / OVERGEN（泛化过头）/ SIBLING / WRONG_LOC / OTHER
  - fine_feature：自下而上的具体特征名（≤15 字，如「并列 copy 方法漏改」「URL 尾斜杠规范化」「同行 heredoc 标记」），不要套固定表
- L2_why（DS 为什么没做对，依据 run*_trajectory.md 的步骤）：
  - steps：工具调用步数；ran_tests：是否跑过测试；edited_tests：是否改了/加了测试
  - searched_callers_or_siblings：有没有搜被改函数的调用点或并列实现（yes/no + 步骤号）
  - read_relevant_existing_tests：有没有读与该行为相关的现有测试（yes/no + 步骤号）
  - process_failure：从下面选最主要的 1 个并写一句证据：
    stopped_early（很快收工、没验证边界）/ followed_issue_literally（照题面字面做，没质疑）/ no_sibling_search（没找并列实现）/ wrong_root_cause（定位错）/ self_tests_too_weak（自己写的测试没覆盖关键情况）/ misread_existing_behavior（误解现有行为）/ other
- L3_predictable（动手前能不能看出来）：
  - visible_in：issue / repo / none
  - evidence：具体证据——题面原句，或基线代码里的 文件:行号（如 "src/objects/Line.js: copy() 与 Mesh.copy 并列"）。看不到写 none
  - pre_run_question：如果预测员事前问这一个问题就能发现风险，这个问题是什么（≤30 字）
- confidence：high/med/low；env_suspect：true/false

材料：题面、标准答案（仅事后用）、两次 DS 补丁、测试结果、run*_trajectory.md（DS 过程摘要）。不要用对上游的记忆。证据写不出就写 none，不要编。
