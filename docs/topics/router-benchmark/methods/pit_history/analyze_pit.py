#!/usr/bin/env python3
"""坑级历史结果：与 14 家公开难度相关、14 家平均 AUC、DS AUC；配对重抽样差值。"""
import json, glob, os, numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
ROOT = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(ROOT)
D = json.load(open(f"{S}/tagging/tag_data.json")); FOLD = json.load(open(f"{S}/refjudge/repo_fold.json"))
subs = [json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
def load(d): return {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(d + "/*.json")}
J = {"档案+Haiku（现有）": load(f"{ROOT}/out_judge_full/dos_haiku"), "坑级·不给历史": load(f"{ROOT}/out_pit/judge_nohist_haiku"),
     "坑级·给踩坑表": load(f"{ROOT}/out_pit/judge_hist_haiku"), "档案+Sonnet（现有最好）": load(f"{ROOT}/out_judge_full/dos_sonnet"),
     "档案+踩坑表+Haiku（整体判）": load(f"{ROOT}/out_pit/judge_dostable_haiku")}
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(f"{ROOT}/out_pit/extract/*.json")}
T = {f: json.load(open(f"{ROOT}/out_pit/table_fold{f}.json")) for f in set(FOLD.values())}
ts = sorted(t for t in EXT if all(t in j for j in J.values()) and all(t in s for s in subs))
y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts]); diff = np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts])
A = {k: np.array([float(j[t]["p_fail"]) for t in ts]) for k, j in J.items()}
def comb(name, g):
    A[name] = np.array([g(t) for t in ts])
for arm in ("nohist", "hist"):
    lab = "不给历史" if arm == "nohist" else "给踩坑表"
    comb(f"坑级·{lab}·单坑最大", lambda t, a=arm: max([float(p["p"]) for p in J["坑级·" + lab][t].get("per_pit", [])] or [0]))
def prior(t):  # 纯历史：按坑类型查另一折的踩坑率，1-∏(1-率)
    o = T[[x for x in T if x != FOLD[D[t]["repo"]]][0]]
    return 1 - np.prod([1 - (o[p["type"]]["nf"] + .5) / (o[p["type"]]["nf"] + o[p["type"]]["na"] + 1) for p in EXT[t] if p["type"] in o])
comb("纯历史：按坑类型查踩坑率（不调模型）", prior)
def ev(p, i):
    return (spearmanr(p[i], diff[i])[0], np.mean([roc_auc_score([0 if s[ts[k]]["resolved"] else 1 for k in i], p[i]) for s in subs]), roc_auc_score(y[i], p[i]))
I = np.arange(len(ts)); print(f"n={len(ts)}  DS 失败 {y.sum()}")
for k, p in A.items():
    s, a, d = ev(p, I); print(f"{k:34s} 相关 {s:+.3f}  14家AUC {a:.3f}  DS AUC {d:.3f}")
rng = np.random.default_rng(0); B = [rng.integers(0, len(ts), len(ts)) for _ in range(1000)]
for a, b in (("坑级·给踩坑表", "坑级·不给历史"), ("坑级·给踩坑表", "档案+Haiku（现有）"), ("坑级·不给历史", "档案+Haiku（现有）"), ("坑级·给踩坑表", "档案+Sonnet（现有最好）"), ("档案+踩坑表+Haiku（整体判）", "档案+Haiku（现有）")):
    for m, nm in ((0, "相关"), (2, "DS AUC")):
        dd = [ev(A[a], i)[m] - ev(A[b], i)[m] for i in B] if m == 0 else [roc_auc_score(y[i], A[a][i]) - roc_auc_score(y[i], A[b][i]) for i in B]
        print(f"{a} − {b} {nm} 95%区间 {np.round(np.percentile(dd, [2.5, 97.5]), 3)}")
