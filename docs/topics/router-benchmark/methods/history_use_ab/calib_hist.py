#!/usr/bin/env python3
"""历史用法 b：用历史成败做校准（不花调用）。两折按仓库交叉：在一折上学，另一折上评。
  raw   : 原始 p_fail
  base  : 只平移整体偏置（logit 加常数，使训练折平均预测 = 训练折历史失败率）
  platt : logit 上的线性变换 a*logit(p)+b（Platt 缩放）
指标：Brier、LogLoss、ECE(10 箱)、AUC（排序不变应几乎不动）。标签 = DS 历史成败（passes<runs 记失败）。"""
import json, glob, os, sys, numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(f"{S}/tagging/tag_data.json")); FOLD = json.load(open(f"{S}/refjudge/repo_fold.json"))
def arm(d):
    P = {}
    for f in glob.glob(d + "/*.json"):
        r = json.load(open(f))
        if "p_fail" in r: P[r.get("task", os.path.basename(f)[:-5])] = float(r["p_fail"])
    return P
ARMS = {"档案+Haiku": f"{S}/dossier/out_judge_full/dos_haiku", "档案+Sonnet": f"{S}/dossier/out_judge_full/dos_sonnet",
        "档案+案例+Haiku": f"{S}/dossier/out_judge_full/case_haiku", "Sonnet读仓库(强基线)": f"{S}/train_tags/out/sonnet_tags"}
for extra in sys.argv[1:]: ARMS[os.path.basename(extra)] = extra
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
sg = lambda z: 1 / (1 + np.exp(-z))
def ece(p, y, k=10):
    b = np.minimum((p * k).astype(int), k - 1)
    return sum(abs(p[b == i].mean() - y[b == i].mean()) * (b == i).mean() for i in range(k) if (b == i).any())
def met(p, y):
    p = np.clip(p, 1e-3, 1 - 1e-3)
    return dict(brier=np.mean((p - y) ** 2), ll=-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)), ece=ece(p, y), auc=roc_auc_score(y, p), mean=p.mean())
for name, d in ARMS.items():
    A = arm(d); ts = sorted(t for t in A if t in D and D[t]["repo"] in FOLD)
    y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts]); p = np.array([A[t] for t in ts]); fo = np.array([FOLD[D[t]["repo"]] for t in ts])
    out = {k: np.zeros_like(p) for k in ("raw", "base", "platt")}
    for f in set(fo):
        tr, te = fo != f, fo == f
        out["raw"][te] = p[te]
        z = lg(p[tr]); c = 0.0
        for _ in range(200):  # 找常数 c 使 mean(sigmoid(z+c)) = 训练折失败率
            c += (y[tr].mean() - sg(z + c).mean()) * 4
        out["base"][te] = sg(lg(p[te]) + c)
        m = LogisticRegression(C=1e6).fit(lg(p[tr])[:, None], y[tr]); out["platt"][te] = m.predict_proba(lg(p[te])[:, None])[:, 1]
    print(f"\n{name}  n={len(ts)}  DS失败率={y.mean():.3f}")
    out["const"] = np.zeros_like(p)
    for f in set(fo): out["const"][fo == f] = y[fo != f].mean()  # 只用历史失败率、不看题
    rng = np.random.default_rng(0); B = [rng.integers(0, len(y), len(y)) for _ in range(2000)]
    bs = lambda a, b: np.percentile([np.mean((out[a][i] - y[i]) ** 2) - np.mean((out[b][i] - y[i]) ** 2) for i in B], [2.5, 97.5])
    print("  Brier 差 95%区间：base−raw", np.round(bs("base", "raw"), 4), " base−const", np.round(bs("base", "const"), 4))
    for k, q in out.items():
        if k == "const": print(f"  const  Brier {np.mean((q-y)**2):.4f}  ECE {ece(q,y):.4f}"); continue
        r = met(q, y); print(f"  {k:6s} Brier {r['brier']:.4f}  LogLoss {r['ll']:.4f}  ECE {r['ece']:.4f}  AUC {r['auc']:.3f}  平均预测 {r['mean']:.3f}")
