"""v3 270 道预检：语言能否判定（老流水线预热方式）、评测镜像是否存在（Hub 网页接口，不计下载次数）、Python 题是否有 conda 环境。不跑模型。"""
import csv, json, os, sys, time, urllib.request, collections
sys.argv = ["x"]; sys.path.insert(0, ".")
import claw_iso_rb as CI
out = []
for r in csv.DictReader(open("split_ds_single_v3_20261114.csv")):
    t = r["instance_id"]; x = dict(r)
    try: x["lang"] = CI.lang_of(t)
    except KeyError: x["lang"] = None
    repo = "sweb.eval.x86_64." + t.replace("__", "_1776_")
    try:
        urllib.request.urlopen(f"https://hub.docker.com/v2/repositories/swebench/{repo}/tags/latest", timeout=30).read(); x["image_ok"] = True
    except Exception as e: x["image_ok"] = False
    x["conda_env"] = os.path.isdir(f"/opt/sbx/conda/{t}") if x["lang"] == "python" else None
    x["ready"] = bool(x["lang"]) and x["image_ok"] and x["conda_env"] is not False
    out.append(x); time.sleep(0.3)
json.dump(out, open("preflight_v3.json", "w"), ensure_ascii=False, indent=1)
print("ready", sum(x["ready"] for x in out), "/", len(out))
print("no_lang_repos", collections.Counter(x["repo"] for x in out if not x["lang"]).most_common())
print("no_image", [x["instance_id"] for x in out if not x["image_ok"]][:10])
print("python_no_env", sum(1 for x in out if x["conda_env"] is False))
print("ready_by_group", collections.Counter(x["group"] for x in out if x["ready"]))
