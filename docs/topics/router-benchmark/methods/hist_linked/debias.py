#!/usr/bin/env python3
"""去偏检验（无新调用）：把判断者 p_fail 里由「档案长度、坑数、第6/7节长度、修复行数」牵引的部分去掉，再看对 DS 成败的准度。
在一折上学去偏回归、另一折上用（和历史学习同口径）。再加上判断者没用上的 T4（题面误导坑数）。"""
import json, glob, os, re, numpy as np
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LinearRegression, LogisticRegression
R = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(R)
D = json.load(open(f"{S}/tagging/tag_data.json")); FO = json.load(open(f"{S}/refjudge/repo_fold.json"))
load = lambda d: {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(f"{R}/{d}/*.json")}
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(f"{R}/out_pit/extract/*.json")}
dos = lambda t: open(f"{R}/out_dossier/{t}.md").read()
def sec(t, n):
    m = re.search(rf"(?:【{n}[^】]*】|#+\s*{n}[^\n]*\n)(.*?)(?=【{n+1}|#+\s*{n+1}|\Z)", dos(t), re.S); return m.group(1) if m else ""
def feats(t): return [np.log(len(dos(t))), len(EXT[t]), np.log1p(len(sec(t, 6))), np.log1p(len(sec(t, 7))), np.log1p(len(D[t].get("gold", "").splitlines())), sum(p["type"] == "T2" for p in EXT[t])]
for name, d in (("档案+Sonnet", "out_judge_full/dos_sonnet"), ("档案+Haiku", "out_judge_full/dos_haiku")):
    P = load(d); ts = sorted(t for t in EXT if t in D and t in P and D[t]["repo"] in FO)
    y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts]); p = np.array([P[t] for t in ts]); fo = np.array([FO[D[t]["repo"]] for t in ts])
    X = np.array([feats(t) for t in ts]); X = (X - X.mean(0)) / X.std(0); t4 = np.array([sum(q["type"] == "T4" for q in EXT[t]) for t in ts], float)
    res = np.zeros(len(ts)); res2 = np.zeros(len(ts))
    for f in set(fo):
        tr, te = fo != f, fo == f
        m = LinearRegression().fit(X[tr], p[tr]); res[te] = p[te] - m.predict(X[te])      # 去掉由篇幅/规模牵引的部分
        res2[te] = res[te] + 0.5 * res[tr].std() * (t4[te] - t4[tr].mean()) / (t4[tr].std() + 1e-9)  # 再补 T4（固定权重，不看标签）
    rng = np.random.default_rng(0); B = [rng.integers(0, len(ts), len(ts)) for _ in range(1000)]
    auc = lambda s, i: roc_auc_score(y[i], s[i]) if len(set(y[i])) == 2 else .5
    print(f"{name} n={len(ts)}  原始 AUC {auc(p,slice(None)) if False else roc_auc_score(y,p):.3f} | 去篇幅/规模牵引 {roc_auc_score(y,res):.3f} | 再补 T4 {roc_auc_score(y,res2):.3f}")
    for lab, s in (("去牵引−原始", res), ("去牵引+T4−原始", res2)):
        d = [auc(s, i) - auc(p, i) for i in B]; print(f"   {lab} 区间 {np.round(np.percentile(d,[2.5,97.5]),3)}")
    # 牵引部分本身能否预示：只用篇幅/规模回归出的部分
    print(f"   只用篇幅/规模预测 DS 挂的 AUC（交叉）{roc_auc_score(y, np.concatenate([LogisticRegression(C=1).fit(X[fo!=f], y[fo!=f]).decision_function(X[fo==f]) for f in sorted(set(fo))])[np.argsort(np.concatenate([np.where(fo==f)[0] for f in sorted(set(fo))]))]):.3f}")
