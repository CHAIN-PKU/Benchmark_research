#!/usr/bin/env python3
"""查证/判断拆分实验：只给「题面 + 某个预测员查到的证据（去掉它的概率和风险分）」，让另一个模型只做判断，不读仓库。
用法：judge_swap.py <证据来源目录名> <判断模型> <输出tag> [--jobs N]"""
import sys, os, json, glob, pathlib, re, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent
src, model, tag = sys.argv[1], sys.argv[2], sys.argv[3]
jobs = int(sys.argv[5]) if len(sys.argv) > 5 else 4
out = ROOT / "out_judge" / tag; out.mkdir(parents=True, exist_ok=True)
FEWSHOT = open(ROOT / "fewshot_v1.md").read()
EXCL = set(json.load(open(ROOT / "fewshot_v1_tasks.json")))
PROMPT = """你是「动手前预测器」的判断环节。另一位调查员已经在仓库里查过这道题，下面是题面和它找到的证据（只有证据，没有它的结论）。
请只根据题面和这些证据，判断一个编程智能体（照题面实现、通常只为题面例子写自测）修好这道题并通过维护者隐藏测试的难度，给出失败概率。不要使用对上游修法的记忆。
请列出影响难度的主要因素（每条说明方向和分量），再给出失败概率。只输出一行 JSON：{{"task":"{task}","factors":[{{"factor":"影响难度的因素（≤20字）","direction":"更难/更容易","weight":"大/中/小","evidence_used":"引用了哪条证据"}}],"main_reason":"一句话说清最关键的判断依据（≤60字）","p_fail":0~1}}

{fewshot}
===== 题面 =====
{issue}
===== 调查员找到的证据 =====
{evidence}
"""
def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "p_fail" in obj:
            return obj
    raise ValueError("no json")
def one(f):
    r = json.load(open(f)); t = r["task"]
    if (out / f"{t}.json").exists(): return t, "skip"
    ev = r.get("evidence") or []
    ev = "\n".join(f"- {e}" for e in (ev if isinstance(ev, list) else [ev]))
    prompt = PROMPT.format(fewshot=FEWSHOT, task=t, issue=(ROOT / "issue" / f"{t}.md").read_text()[:6000], evidence=ev)
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        row = extract(json.loads(p.stdout).get("result", "")); row["task"] = t
        (out / f"{t}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n"); return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:]); return t, "err"
files = [f for f in sorted(glob.glob(str(ROOT / "out" / src / "*.json"))) if pathlib.Path(f).stem not in EXCL]
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, files): print(t, s, flush=True)
