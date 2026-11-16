"""80 道全量预检：题在题库里、语言能判、评测镜像在 Docker Hub 上能找到。不跑模型。"""
import csv, json, subprocess, sys
sys.argv = ["x"]; sys.path.insert(0, ".")
import claw_iso_rb as CI
out = []
for r in csv.DictReader(open("run_order_v1.csv")):
    t = r["instance_id"]; rec = {"task": t, "batch": r["batch"]}
    rec["in_dataset"] = t in CI.ROWS
    try: rec["lang"] = CI.lang_of(t)
    except KeyError: rec["lang"] = None
    img = f"swebench/sweb.eval.x86_64.{t.replace(chr(95)*2, '_1776_')}:latest"
    p = subprocess.run(["docker", "manifest", "inspect", img], capture_output=True, text=True, timeout=60)
    rec["image_ok"] = p.returncode == 0
    rec["conda_env"] = (CI.lang_of(t) == "python" and __import__("os").path.isdir(f"/opt/sbx/conda/{t}")) if rec["lang"] == "python" else None
    rec["ok"] = rec["in_dataset"] and rec["lang"] is not None and rec["image_ok"] and rec["conda_env"] is not False
    out.append(rec)
json.dump(out, open("preflight.json", "w"), ensure_ascii=False, indent=1)
for x in out:
    if not x["ok"]: print("NOT_OK", x)
print("ok", sum(x["ok"] for x in out), "/", len(out))
