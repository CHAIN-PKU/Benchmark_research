#!/usr/bin/env python3
"""基线复现（Agent Psychometrics 思路）：LLM 按固定评分细则给题打分，之后用回归合成（见 fit_eval.py）。
用法：rubric_score.py <fair|oracle> <old|rb> <模型> [--jobs N]
fair = 只给题面；oracle = 题面 + 标准答案 + 隐藏测试（论文原版设定）。不读仓库、单轮、禁工具。"""
import sys, json, pathlib, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
mode, split, model = sys.argv[1], sys.argv[2], sys.argv[3]; jobs = int(sys.argv[5]) if len(sys.argv) > 5 else 4
out = ROOT / "out" / f"{mode}_{split}"; out.mkdir(parents=True, exist_ok=True)
KEYS = ["scope", "clarity", "repro", "domain", "code_breadth", "edge_cases", "test_strictness", "conventions", "new_feature"]
RUBRIC = """请按下面 9 条标准，给这道真实仓库任务打分（1~5 分，5 = 该项最突出）。只打分，不要做题。
scope：正确修改需要改动的范围有多大（文件、函数数量）。
clarity：题面把期望行为说得有多清楚（5 = 非常清楚）。
repro：题面是否给出可复现的例子或明确的期望输出（5 = 给得很完整）。
domain：需要多少领域知识或外部规范（协议、标准、参考实现）。
code_breadth：需要理解多大范围的现有代码。
edge_cases：正确实现需要处理多少边界情况。
test_strictness：维护者的测试可能有多严格、多细（会不会检查题面没写的细节）。
conventions：需要遵守多少仓库已有的约定或并列实现。
new_feature：这是新增功能（5）还是修已有 bug（1）。
只输出一行 JSON：{{"scope":n,"clarity":n,"repro":n,"domain":n,"code_breadth":n,"edge_cases":n,"test_strictness":n,"conventions":n,"new_feature":n}}

===== 题面 =====
{issue}
{extra}"""
def load(split):
    if split == "old":
        d = json.load(open(S / "tagging/tag_data.json"))
        return {t: (v["issue"], v.get("gold", ""), v.get("test", "")) for t, v in d.items()}
    res = {}
    for t in json.load(open(S / "expcard/../rebench/tasks.json")):
        c = json.load(open(ROOT / "gold_rb" / t / "tests/config.json"))
        res[t] = ((S / "rebench/issue" / f"{t}.md").read_text(), c.get("patch", ""), c.get("test_patch", ""))
    return res
def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and all(k in obj for k in KEYS):
            return {k: float(obj[k]) for k in KEYS}
    raise ValueError("no json")
DATA = load(split)
def one(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    issue, gold, test = DATA[t]
    extra = "" if mode == "fair" else f"===== 标准修复 =====\n{gold[:8000]}\n===== 隐藏测试 =====\n{test[:8000]}\n"
    p = subprocess.run(["claude", "-p", RUBRIC.format(issue=issue[:6000], extra=extra), "--output-format", "json",
                        "--model", model, "--max-turns", "1", "--setting-sources", "", "--strict-mcp-config",
                        "--disable-slash-commands", "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        row = extract(json.loads(p.stdout).get("result", "")); row["task"] = t
        (out / f"{t}.json").write_text(json.dumps(row) + "\n"); return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:]); return t, "err"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, sorted(DATA)): print(t, s, flush=True)
