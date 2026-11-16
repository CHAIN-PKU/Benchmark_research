#!/usr/bin/env python3
"""「查」vs「掂量」：DS 挂的题按档案是否写到真实失败点分三类，看判断者给这些题的 p_fail 在「DS 做对的题」里排第几（百分位）。
百分位高 = 判断者把它排在多数做对题之前（掂量对了）。"""
import json, glob, os, numpy as np
from collections import Counter
ROOT = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(ROOT)
D = json.load(open(f"{S}/tagging/tag_data.json"))
F = {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(f"{ROOT}/out_found/*.json")}
def arm(d): return {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(d + "/*.json")}
fail = lambda t: D[t]["passes"] < D[t]["runs"]
print("n =", len(F), Counter(v["found"] for v in F.values()), "节:", Counter(v["section"] for v in F.values() if v["found"] != "miss"))
for name, d in (("档案+Sonnet", f"{ROOT}/out_judge_full/dos_sonnet"), ("档案+Haiku", f"{ROOT}/out_judge_full/dos_haiku")):
    P = arm(d); passes = np.array([P[t] for t in P if not fail(t)])
    print(f"\n{name}：做对题 p_fail 中位 {np.median(passes):.2f}")
    for k in ("hit", "partial", "miss"):
        ts = [t for t in F if F[t]["found"] == k and t in P]
        if not ts: continue
        pct = [np.mean(passes < P[t]) + 0.5 * np.mean(passes == P[t]) for t in ts]
        print(f"  {k:7s} {len(ts):2d} 道  p_fail 中位 {np.median([P[t] for t in ts]):.2f}  在做对题中的平均百分位 {np.mean(pct):.2f}（=该类的 AUC）  排进前 25% 的 {np.mean(np.array(pct) >= .75):.0%}")
