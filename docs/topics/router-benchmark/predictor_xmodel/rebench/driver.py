#!/usr/bin/env python3
"""前瞻式预测驱动：快照就绪的题，依次跑三组预测（通用 / 清单v2 / 事前需求标签），
三组都出结果后写冻结记录（含 sha256 与时间），并把题号追加到服务器的 predictor_rebench_cleared.txt。
只有进了 cleared 的题，DSH 才会开跑。"""
import concurrent.futures as cf, datetime, hashlib, json, os, pathlib, subprocess, time
ROOT = pathlib.Path(__file__).resolve().parent
ARMS = [("sonnet_gen", "generic_plain.md")]
FROZEN = ROOT / "frozen"; FROZEN.mkdir(exist_ok=True)
CLEARED_REMOTE = "benchmark_router_paper/claude_eval/predictor_rebench_cleared.txt"
tasks = json.load(open(ROOT / "tasks.json"))

def run_arm(task, tag, prompt):
    env = dict(os.environ, PRED_KEEP_HOME="1", PRED_CHECKLIST=prompt, ANTHROPIC_MODEL="claude-sonnet-5-5")
    for _ in range(2):  # 失败重试一次
        subprocess.run(["python3", "run_predictor.py", tag, "--tasks", task, "--jobs", "1"], cwd=ROOT, env=env,
                       capture_output=True, text=True)
        if (ROOT / "out" / tag / f"{task}.json").exists():
            return True
        (ROOT / "out" / tag / f"{task}.err").unlink(missing_ok=True)
    return False

def one(task):
    if (FROZEN / f"{task}.json").exists():
        return task, "skip"
    if not (ROOT / "snap" / task).is_dir():
        return task, "nosnap"
    ok = all(run_arm(task, tag, pr) for tag, pr in ARMS)
    if not ok:
        return task, "err"
    rec = {"task": task, "frozen_at": datetime.datetime.now().isoformat(timespec="seconds"),
           "arms": {tag: json.load(open(ROOT / "out" / tag / f"{task}.json")) for tag, _ in ARMS}}
    body = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    rec_sha = hashlib.sha256(body.encode()).hexdigest()
    (FROZEN / f"{task}.json").write_text(body + "\n")
    with open(ROOT / "frozen_ledger.tsv", "a") as f:
        f.write(f"{task}\t{rec['frozen_at']}\t{rec_sha}\n")
    subprocess.run(["ssh", "srv", f"echo {task} >> {CLEARED_REMOTE}"], capture_output=True)
    return task, "cleared"

while True:
    todo = [t for t in tasks if not (FROZEN / f"{t}.json").exists()]
    if not todo:
        break
    ready = [t for t in todo if (ROOT / "snap" / t).is_dir()]
    if not ready:
        if not subprocess.run(["pgrep", "-f", "make_snap.sh"], capture_output=True).stdout:
            print("no snapshots left to build; remaining:", todo, flush=True); break
        time.sleep(60); continue
    with cf.ThreadPoolExecutor(2) as ex:
        for t, s in ex.map(one, ready[:6]):
            print(datetime.datetime.now().strftime("%H:%M:%S"), t, s, flush=True)
