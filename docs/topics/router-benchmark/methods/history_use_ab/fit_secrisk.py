#!/usr/bin/env python3
"""历史用法 a：用另一折仓库的历史成败学「7 节风险分各占多少分量」，在本折上评。
对比：同一次调用的整体 p_fail（判断者自己掂量）、7 节等权平均、学到的权重（DS 历史 / 14 家公开历史）。
评价：与 14 家公开平均难度的秩相关、14 家平均 AUC、DS AUC。"""
import json, glob, os, sys, numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression, Ridge
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = json.load(open(f"{S}/tagging/tag_data.json")); FOLD = json.load(open(f"{S}/refjudge/repo_fold.json"))
subs = [json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
d = sys.argv[1] if len(sys.argv) > 1 else f"{S}/dossier/out_secrisk/haiku"
R = {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(d + "/*.json")}
ts = sorted(t for t in R if D[t]["repo"] in FOLD and all(t in s for s in subs))
K = [f"r{i}" for i in range(1, 8)]
X = np.array([[float(R[t][k]) for k in K] for t in ts]); pf = np.array([float(R[t]["p_fail"]) for t in ts])
y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts]); fo = np.array([FOLD[D[t]["repo"]] for t in ts])
diff = np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts])
def ev(p, idx=None):
    idx = np.arange(len(ts)) if idx is None else idx
    au = np.mean([roc_auc_score([0 if s[ts[i]]["resolved"] else 1 for i in idx], p[idx]) for s in subs
                  if len({s[ts[i]]["resolved"] for i in idx}) == 2])
    return spearmanr(p[idx], diff[idx])[0], au, roc_auc_score(y[idx], p[idx])
arms = {"判断者整体 p_fail": pf, "7 节等权平均": X.mean(1)}
for name, target, kind in (("学权重：DS 历史", y, "lr"), ("学权重：14 家公开历史", diff, "ridge"), ("学权重：DS 历史 + p_fail", y, "lr+")):
    o = np.zeros(len(ts)); W = []
    for f in set(fo):
        tr, te = fo != f, fo == f
        Z = np.c_[X, pf] if kind == "lr+" else X
        m = (LogisticRegression(C=1.0) if kind.startswith("lr") else Ridge(alpha=1.0)).fit(Z[tr], target[tr])
        o[te] = m.decision_function(Z[te]) if kind.startswith("lr") else m.predict(Z[te]); W.append(m.coef_.ravel())
    arms[name] = o; print(name, "权重(两折平均)", np.round(np.mean(W, 0), 2))
print(f"\nn={len(ts)}  DS 失败 {y.sum()}")
print("各节单独：与公开难度相关 / DS AUC")
for i, k in enumerate(K): print(f"  {k} {spearmanr(X[:, i], diff)[0]:+.3f}  {roc_auc_score(y, X[:, i]):.3f}")
for name, p in arms.items():
    s, a, ds = ev(p); print(f"{name:22s} 相关 {s:+.3f}  14家AUC {a:.3f}  DS AUC {ds:.3f}")
rng = np.random.default_rng(0); B = [rng.integers(0, len(ts), len(ts)) for _ in range(1000)]
for a in ("学权重：DS 历史", "学权重：14 家公开历史"):
    dd = [spearmanr(arms[a][i], diff[i])[0] - spearmanr(pf[i], diff[i])[0] for i in B]
    print(f"{a} − 整体 p_fail（相关）95%区间 {np.round(np.percentile(dd, [2.5, 97.5]), 3)}")
