#!/usr/bin/env python3
"""立即清一轮：已完成（≥2 份有效 dsh 结果）且没在跑的题：删 rb_* 工作区、tpl、镜像。"""
import json, pathlib, subprocess, shutil
HERE = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot")
RUNS, TPL = HERE/"runs", HERE/"tpl"

def running(task):
    r = subprocess.run(["pgrep","-af","ds_pilot.py run " + task], capture_output=True, text=True)
    return bool(r.stdout.strip())

def done(task):
    n = 0
    for rep in sorted((RUNS/task).glob("dsh_r*")):
        if (rep/"INVALID.json").exists(): continue
        rp = rep/"record.json"
        if not rp.exists(): continue
        try: d = json.loads(rp.read_text())
        except Exception: continue
        if "resolved" in d: n += 1
    return n

act = []
for tdir in sorted(RUNS.iterdir() if RUNS.exists() else []):
    if not tdir.is_dir(): continue
    task = tdir.name
    if done(task) < 2 or running(task): continue
    t = TPL/task
    if t.is_dir() and t.resolve().parent == TPL.resolve():
        subprocess.run(["sudo","rm","-rf",str(t)], capture_output=True); act.append("tpl:"+task)
    pat = "/home/coder/chains/rb_" + task + "*"
    subprocess.run("sudo rm -rf " + pat, shell=True)
    act.append("chain:"+task)
    if "__" in task:
        owner, rest = task.split("__",1)
        img = "swebench/sweb.eval.x86_64.%s_1776_%s:latest" % (owner, rest)
        subprocess.run(["sudo","docker","rmi",img], capture_output=True)
        act.append("img:"+task)
print("cleaned", len(act), "actions")
for a in act: print(" ", a)
