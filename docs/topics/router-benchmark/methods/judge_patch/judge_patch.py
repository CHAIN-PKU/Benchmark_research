#!/usr/bin/env python3
"""事后判卷：只给题面 + 别人（DS）提交的补丁，不读仓库、不跑测试，判断补丁能否通过维护者隐藏测试。
用法：judge_patch.py <模型> <输出tag> [jobs]"""
import sys, os, json, re, pathlib, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent
model, tag = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 3
out = ROOT / "out" / tag; out.mkdir(parents=True, exist_ok=True)
PROMPT = """下面是一个开源仓库的问题描述（issue），以及另一个编程智能体为它提交的修改补丁。
请判断这个补丁能否通过维护者的隐藏测试（这些测试你看不到；你也不能运行代码）。考虑：补丁是否真正解决了问题、是否漏掉了题面没明说但很可能被测试检查的情况、是否可能破坏已有行为。
不要使用你对这个项目上游真实修法的记忆。
只输出一行 JSON：{{"task":"{task}","p_pass":0~1,"main_reason":"≤50字"}}

===== issue =====
{issue}
===== 补丁 =====
{patch}
"""
def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try: obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError: continue
        if isinstance(obj, dict) and "p_pass" in obj: return obj
    raise ValueError("no json")
def one(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    prompt = PROMPT.format(task=t, issue=(ROOT/"issue"/f"{t}.md").read_text()[:6000], patch=(ROOT/"patches"/f"{t}.diff").read_text()[:12000])
    p = subprocess.run(["claude","-p",prompt,"--output-format","json","--model",model,"--max-turns","1","--setting-sources","",
                        "--strict-mcp-config","--disable-slash-commands","--disallowedTools","Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        r = extract(json.loads(p.stdout).get("result","")); r["task"] = t
        (out/f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)+"\n"); return t, "ok"
    except Exception as e:
        (out/f"{t}.err").write_text(str(e)+"\n"+p.stdout[-1500:]); return t, "err"
tasks = json.load(open(ROOT/"tasks.json"))
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, tasks): print(t, s, flush=True)
