# Benchmark 造题框架参考（调研笔记）

日期：2026-11-12 · 作者：DSH · 状态：调研，未开始正式造题

目的：我们后面要搭 benchmark，但先不要自己从零发明流程。下面 4 个公开框架/流程
是社区里真正在用的，逐个说清：怎么造题、怎么判分、怎么防泄题/防刷分，
以及哪些我们以后能直接复用。每个段落末尾是「可复用」，最后一节是汇总。

## 1. SWE-bench：从真实 PR 造题的流程范本

来源：[swebench.com](https://www.swebench.com/original.html)、[论文 arXiv:2310.06770](https://arxiv.org/abs/2310.06770)

**怎么造题**：爬 GitHub 上 12 个热门 Python 仓库的 Pull Request 和 Issue，
只保留同时满足两条的 PR：(1) 关联一个 issue；(2) 改动里包含 1 个以上测试文件。
这样凑出 2,294 个任务。每个任务用 Docker 镜像固定「PR 合入前」的代码环境和依赖，
保证谁跑都是同一份环境。

**怎么判分**：不看模型写的代码像不像，只看测试。每个任务有一组
Fail-to-Pass 测试：在 PR 合入前这组测试失败，合入后通过。模型给出 patch 之后，
就把这组测试跑一遍，全过算解决。评测框架里还配了 Pass-to-Pass 测试，
用来确认改动没有把原本能过的测试弄坏。

**怎么防泄题/防刷分**：靠「判分逻辑不在被测 agent 手里」——测试和答案在评测环境里，
agent 只能改代码。官方后来出了 SWE-bench Verified（500 条人工筛过、可解性确认过），
用来减少「题本身有问题」的噪声。但这套防护不是绝对安全：BenchJack 的审计发现，
agent 可以直接注入 `conftest.py` 里的 pytest hook 让全部测试通过（见第 4 节）。

**可复用**：
- 「真实来源 + 天然带判分信号」的造题思路：从真实数据/真实 bug/真实 issue 出题，
  判分用已有的测试或校验器，不自己发明主观标准。
- 「一套题一个固定环境」：题目和运行环境一起冻结，结果才可复现。

## 2. Inspect AI：一个任务 = 数据集 + 解题器 + 判分器

来源：[inspect.aisi.org.uk/tasks](https://inspect.aisi.org.uk/tasks.html)（UK AISI 维护）

**怎么造题**：写一个 `@task` 函数，返回 `Task(dataset=..., solver=..., scorer=...)`。
数据从 JSON/HuggingFace 数据集读；`solver` 是解题流程（可以简单到「直接生成」，
也可以是带 `bash`/`python` 工具、多轮 ReAct 的 agent）；scorer 负责判分，
可以用规则匹配，也可以让另一个模型当裁判（model-graded）。
题目的参数（提示词、裁判模型等）可以命令行覆盖，同一个任务能跑不同变体。

**怎么判分**：`scorer` 决定。常见是精确匹配、包含匹配，或者 `model_graded_fact`
让裁判模型判断。支持 sandbox 配置（如 Docker），把不可信代码放到隔离环境里跑，
这对 agent 类评测很关键。跑完有结构化日志和网页查看器，能逐条看模型为什么错。

**怎么防泄题/防刷分**：自带沙箱机制隔离被测代码；用模型当裁判时要防提示注入
（BenchJack 的 V4 类问题）；它的定位是「评测基础设施」，泄题防护要靠出题人自己
（答案不要放进 agent 能读到的目录）。

**可复用**：
- 我们的题如果涉及「让 agent 动手做多步任务」，直接照它的「数据集 + 解题器 + 判分器」
  三件套来组织，天然支持多模型对比和逐条复盘。
- 沙箱配置的方式可以抄：不可信代码一律进沙箱跑。

## 3. lm-evaluation-harness：YAML 配置的静态题工厂

来源：[EleutherAI/lm-evaluation-harness 任务指南](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md)

**怎么造题**：一个任务一个 YAML。核心字段：
- `task` 任务名；`dataset_path`/`dataset_name` 数据集；`test_split` 用哪个切分；
- `doc_to_text` / `doc_to_target` / `doc_to_choice`：把一条样本转成 prompt、答案、选项；
- `output_type`：`generate_until`（生成式）、`loglikelihood`（比概率）、
  `multiple_choice`（选择题）；
- `num_fewshot` 少样本数；`metric_list` 指标（`acc`、`exact_match`、`f1` 等）；
- `filter_list` 后处理（正则抽答案、majority_vote 多数投票等）；
- `metadata.version` 记录任务版本。

同一套模型接口下跑几百个任务，出统一的成绩表，这也是它被学术界大量用的原因。

**怎么判分**：按 `output_type` 选判分方式：选择题比较各选项的对数似然；
生成题用精确匹配/包含匹配/正则抽取后再比；支持多套 filter 管道（比如 self-consistency
的 maj@8 / maj@64 同时报）。

**怎么防泄题/防刷分**：内置去污染开关 `should_decontaminate` +
`doc_to_decontamination_query`，用 n-gram 重叠检查题目是否出现在训练语料里；
但它的题目多是单轮问答，本身不涉及 agent 越权改判分器的问题。

**可复用**：
- 我们如果要做「静态题」（选择题、填空、短答），这套 YAML 结构最省事，
  而且能直接对接主流模型评测。
- 去污染的 n-gram 思路可以单独拿来用。

## 4. BenchJack：造完题之后，审计它能不能被刷

来源：[github.com/benchjack/benchjack](https://github.com/benchjack/benchjack)、
[论文 arXiv:2605.12673](https://arxiv.org/abs/2605.12673)

**它是干什么的**：不是造题框架，是「benchmark 可刷分性扫描器」。把任意 benchmark
仓库丢给它，它用静态分析（Semgrep/Bandit/Hadolint）+ AI 审计（Claude Code/Codex），
找 8 类漏洞（V1–V8）：

| 编号 | 漏洞 | 例子 |
|---|---|---|
| V1 | agent 和判分器没有隔离 | agent 能写判分器读的文件 |
| V2 | 答案随题一起发布 | ground truth 在运行时能读到 |
| V3 | 对不可信输入做 eval/exec | 模型输出直接进 `eval()` |
| V4 | LLM 裁判不防注入 | prompt injection 骗过裁判 |
| V5 | 字符串匹配太弱 | 用 `in` 或宽松正则，部分对就算全对 |
| V6 | 判分逻辑有缺口 | 边界情况/off-by-one |
| V7 | 信任不可信代码的输出 | agent 生成的代码以判分器权限跑 |
| V8 | 给多余权限 | 可联网、可写文件、sudo |

它审计过 8 个主流 agent benchmark（4,458 题），**每一个都能被刷分**，比如
SWE-bench Verified 里注入 `conftest.py` 的 pytest hook 可以做到 100% 通过；
WebArena 用 `file://` 就能读到参考配置里的答案。

**怎么防泄题/防刷分**：它给的是检查清单，不是自动防护。落到设计上就是：
判分逻辑和被测 agent 物理隔离、答案不随题下发、判分不看模型给的「伪证据」、
LLM 裁判要防注入、匹配规则要严格、权限最小化。

**可复用**：
- 我们的题搭好后，先拿 BenchJack 跑一遍，或至少按 V1–V8 手工过一遍清单。
- 写判分器时把 V5（弱匹配）和 V4（裁判注入）当红线。
- 注意它还是 early preview：Docker 沙箱标注 WIP，Codex 后端拒绝率高，
  必须用 Claude Code 后端；所以别把它当唯一防线。

## 汇总：以后怎么用

| 框架 | 定位 | 我们什么时候用 |
|---|---|---|
| SWE-bench | 真实 PR 造题流程 | 设计「从真实数据出题 + 用测试判分」的思路时参考 |
| Inspect AI | 通用评测基础设施（多轮 agent 友好） | 题目要 agent 动手、要沙箱、要逐条复盘时 |
| lm-evaluation-harness | YAML 静态题工厂 | 选择题/短答/生成题，多模型批量对比 |
| BenchJack | 可刷分性审计 | 每批题上线前跑一遍 |

我们自己造题的初步流程（待陈润材确认后再细化，现在不执行）：
1. 选题来源：真实数据/真实 issue/真实论文结论，保证有客观判分信号。
2. 判分：优先确定性校验（测试、精确匹配），必须用 LLM 裁判时加防注入和 schema 校验。
3. 防泄题：答案与判分逻辑不进 agent 可读目录；凡跑不可信代码一律进沙箱。
4. 上线前：按 BenchJack V1–V8 自查一遍，记录检查结果。

参考文献：
- [SWE-bench (ICLR 2024)](https://arxiv.org/abs/2310.06770)
- [Inspect AI 文档](https://inspect.aisi.org.uk/tasks.html)
- [lm-evaluation-harness 任务指南](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md)
- [BenchJack](https://github.com/benchjack/benchjack) / [论文](https://arxiv.org/abs/2605.12673)
