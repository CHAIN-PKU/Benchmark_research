#!/usr/bin/env python3
"""查证/判断拆分实验：只给「题面 + 某个预测员查到的证据（去掉它的概率和风险分）」，让另一个模型只做判断，不读仓库。
用法：judge_swap.py <证据来源目录名> <判断模型> <输出tag> [--jobs N]"""
import sys, os, json, glob, pathlib, re, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent
src, model, tag = sys.argv[1], sys.argv[2], sys.argv[3]
jobs = int(sys.argv[5]) if len(sys.argv) > 5 else 4
out = ROOT / "out_judge" / tag; out.mkdir(parents=True, exist_ok=True)
PROMPT = """你是「动手前预测器」的判断环节。另一位调查员已经在仓库里查过这道题，下面是题面和它找到的证据（只有证据，没有它的结论）。
请只根据题面和这些证据，判断一个编程智能体（照题面实现、通常只为题面例子写自测）修好这道题并通过维护者隐藏测试的难度，给出失败概率。不要使用对上游修法的记忆。
只输出一行 JSON：{{"task":"{task}","p_fail":0~1,"reason":"≤40字"}}

===== 题面 =====
{issue}
===== 调查员找到的证据 =====
{evidence}
"""
def extract(text):
    for m in reversed(list(re.finditer(r"\{[^{}]*\"p_fail\"[^{}]*\}", text, re.S))):
        try: return json.loads(m.group(0))
        except Exception: continue
    raise ValueError("no json")
def one(f):
    r = json.load(open(f)); t = r["task"]
    if (out / f"{t}.json").exists(): return t, "skip"
    ev = r.get("evidence") or []
    ev = "\n".join(f"- {e}" for e in (ev if isinstance(ev, list) else [ev]))
    prompt = PROMPT.format(task=t, issue=(ROOT / "issue" / f"{t}.md").read_text()[:6000], evidence=ev)
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        row = extract(json.loads(p.stdout).get("result", "")); row["task"] = t
        (out / f"{t}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n"); return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:]); return t, "err"
files = sorted(glob.glob(str(ROOT / "out" / src / "*.json")))
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, files): print(t, s, flush=True)
