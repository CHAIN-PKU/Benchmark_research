#!/usr/bin/env python3
"""按 Claude 指定范围清理已完成题目的缓存：
- 只清 ds_pilot/tpl/<题> 和 swebench/sweb.eval.x86_64.<题镜像>
- 判定完成：runs/<题>/dsh_r*/record.json 里有 resolved 且不含 INVALID.json 的 >=2 份
- 正在跑的题跳过
- 每 20 分钟一轮；动作写 cleanup.log
"""
import json, pathlib, subprocess, time, shutil

HERE = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot")
RUNS, TPL = HERE/"runs", HERE/"tpl"
LOG = HERE/"cleanup.log"

def log(msg):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a", encoding="utf-8") as f:
        f.write("[" + stamp + "] " + str(msg) + "\n")

def running(task):
    r = subprocess.run(["pgrep","-af","ds_pilot.py run " + task], capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if "python" in line and "ds_pilot.py run " + task in line:
            return True
    return False

def done_reps(task):
    n = 0
    for rep in sorted((RUNS/task).glob("dsh_r*")):
        if (rep/"INVALID.json").exists():
            continue
        rp = rep/"record.json"
        if not rp.exists():
            continue
        try:
            d = json.loads(rp.read_text())
        except Exception:
            continue
        if "resolved" in d:
            n += 1
    return n

def image_name(task):
    if "__" not in task:
        return None
    owner, rest = task.split("__", 1)
    return "swebench/sweb.eval.x86_64.%s_1776_%s:latest" % (owner, rest)

def sweep():
    freed = 0
    for tdir in sorted(RUNS.iterdir()):
        if not tdir.is_dir():
            continue
        task = tdir.name
        if done_reps(task) < 2:
            continue
        if running(task):
            log("skip running " + task)
            continue
        t = TPL / task
        if t.is_dir() and t.resolve().parent == TPL.resolve():
            try:
                sz = int(subprocess.run(["du","-sk",str(t)],capture_output=True,text=True).stdout.split()[0])
            except Exception:
                sz = 0
            subprocess.run(["sudo","rm","-rf",str(t)], capture_output=True)
            freed += sz
            log("rm tpl " + task + " " + str(sz//1024) + "MB")
        # 清掉已跑完题目的运行工作区（rb_*），避免 chains 持续膨胀
        subprocess.run("sudo rm -rf /home/coder/chains/rb_" + task + "__r*", shell=True, capture_output=True)
        log("rm chains " + task)
        img = image_name(task)
        if img:
            r = subprocess.run(["sudo","docker","rmi",img], capture_output=True, text=True)
            log("rmi " + img + " rc=" + str(r.returncode) + " " + (r.stdout or r.stderr).strip()[:120])
    log("round done freed=" + str(freed//1024) + "MB")

if __name__ == "__main__":
    log("auto_clean started")
    while True:
        try:
            sweep()
        except Exception as e:
            log("error " + type(e).__name__ + ": " + str(e))
        time.sleep(300)
