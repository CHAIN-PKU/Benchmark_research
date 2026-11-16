#!/usr/bin/env python3
"""历史信息各用法总表：排序（相关/14家AUC/DS AUC）+ 概率（Brier/ECE，原始未校准）+ 与无历史同判断者的配对差。"""
import json, glob, os, sys, numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
ROOT = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(ROOT)
D = json.load(open(f"{S}/tagging/tag_data.json")); subs = [json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
def load(d):
    P = {}
    for f in glob.glob(f"{ROOT}/{d}/*.json"):
        try: r = json.load(open(f)); P[r["task"]] = float(r["p_fail"])
        except Exception: pass
    return P
ARMS = [("档案+Haiku（无历史）", "out_judge_full/dos_haiku", None), ("+区分清单（无数字）Haiku", "out_con/score_haiku", 0), ("+历史尺子（清单+挂率）Haiku", "out_con/anchor_haiku", 0),
        ("+历史文案 Haiku", "out_hdoc/judge_haiku", 0), ("档案+Sonnet（无历史）", "out_judge_full/dos_sonnet", None), ("+区分清单 Sonnet", "out_con/score_sonnet", 4), ("+历史文案 Sonnet", "out_hdoc/judge_sonnet", 4)]
A = [(n, load(d), b) for n, d, b in ARMS]; A = [(n, p, b) for n, p, b in A if len(p) > 100]
ts = sorted(t for t in set.intersection(*[set(p) for _, p, _ in A]) if t in D and all(t in s for s in subs))
y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts]); diff = np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts])
def ece(p, k=10):
    b = np.minimum((p * k).astype(int), k - 1); return sum(abs(p[b == i].mean() - y[b == i].mean()) * (b == i).mean() for i in range(k) if (b == i).any())
print(f"n={len(ts)} DS 挂 {y.sum()}")
V = {}
for n, P, b in A:
    p = np.array([P[t] for t in ts]); V[n] = p
    au = np.mean([roc_auc_score([0 if s[t]["resolved"] else 1 for t in ts], p) for s in subs])
    print(f"{n:26s} 相关 {spearmanr(p, diff)[0]:+.3f}  14家AUC {au:.3f}  DS AUC {roc_auc_score(y, p):.3f}  | Brier {np.mean((p - y) ** 2):.3f} ECE {ece(p):.3f} 平均p {p.mean():.2f}")
rng = np.random.default_rng(0); B = [rng.integers(0, len(ts), len(ts)) for _ in range(1000)]
names = [n for n, _, _ in A]
for n, _, b in A:
    if b is None: continue
    base = [m for m in names if ("Haiku" in m) == ("Haiku" in n) and "无历史" in m][0]
    d1 = [spearmanr(V[n][i], diff[i])[0] - spearmanr(V[base][i], diff[i])[0] for i in B]; d2 = [roc_auc_score(y[i], V[n][i]) - roc_auc_score(y[i], V[base][i]) for i in B]
    d3 = [np.mean((V[n][i] - y[i]) ** 2) - np.mean((V[base][i] - y[i]) ** 2) for i in B]
    print(f"{n} − {base}: 相关 {np.round(np.percentile(d1, [2.5, 97.5]), 3)} DS AUC {np.round(np.percentile(d2, [2.5, 97.5]), 3)} Brier {np.round(np.percentile(d3, [2.5, 97.5]), 3)}")
