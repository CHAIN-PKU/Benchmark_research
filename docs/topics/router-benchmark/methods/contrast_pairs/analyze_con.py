#!/usr/bin/env python3
"""区分清单结果：与 14 家难度相关、14 家 AUC、DS AUC；逐条区分力；配对重抽样。"""
import json, glob, os, numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
ROOT = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(ROOT)
D = json.load(open(f"{S}/tagging/tag_data.json")); FOLD = json.load(open(f"{S}/refjudge/repo_fold.json"))
subs = [json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
load = lambda d: {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(d + "/*.json")}
import sys
SC = load(f"{ROOT}/out_con/score_" + (sys.argv[1] if len(sys.argv) > 1 else "haiku")); BH = load(f"{ROOT}/out_judge_full/dos_haiku"); BS = load(f"{ROOT}/out_judge_full/dos_sonnet")
ts = sorted(t for t in SC if t in BH and t in BS and all(t in s for s in subs))
y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts]); diff = np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts])
def imean(t): v = [float(x["s"]) for x in SC[t].get("per_item", [])]; return np.mean(v) if v else .5
A = {"档案+Haiku（现有）": [BH[t]["p_fail"] for t in ts], "区分清单+Haiku p_fail": [SC[t]["p_fail"] for t in ts],
     "区分清单 逐条平均": [imean(t) for t in ts], "档案+Sonnet（现有最好）": [BS[t]["p_fail"] for t in ts]}
A = {k: np.array(v, float) for k, v in A.items()}
def ev(p, i): return spearmanr(p[i], diff[i])[0], np.mean([roc_auc_score([0 if s[ts[k]]["resolved"] else 1 for k in i], p[i]) for s in subs]), roc_auc_score(y[i], p[i])
I = np.arange(len(ts)); print(f"n={len(ts)} DS 挂 {y.sum()}")
for k, p in A.items(): s, a, d = ev(p, I); print(f"{k:24s} 相关 {s:+.3f}  14家AUC {a:.3f}  DS AUC {d:.3f}")
for fo in sorted(set(FOLD.values())):  # 逐条：在用它的那一折（另一折的题）上的 DS AUC
    C = json.load(open(f"{ROOT}/out_con/checklist_fold{fo}.json"))["items"]; te = [k for k, t in enumerate(ts) if FOLD[D[t]["repo"]] != fo]
    print(f"\n清单 fold{fo}（{len(te)} 道上检验）")
    for c in C:
        v = np.array([next((float(x["s"]) for x in SC[ts[k]].get("per_item", []) if int(x["id"]) == c["id"]), .5) for k in te])
        print(f"  {c['id']}. {c['question'][:30]:30s} DS AUC {roc_auc_score(y[te], v):.2f}  与难度相关 {spearmanr(v, diff[te])[0]:+.2f}")
rng = np.random.default_rng(0); B = [rng.integers(0, len(ts), len(ts)) for _ in range(1000)]
for a, base in (("区分清单+Haiku p_fail", "档案+Haiku（现有）"), ("区分清单 逐条平均", "档案+Haiku（现有）"), ("区分清单+Haiku p_fail", "档案+Sonnet（现有最好）")):
    d1 = [spearmanr(A[a][i], diff[i])[0] - spearmanr(A[base][i], diff[i])[0] for i in B]
    d2 = [roc_auc_score(y[i], A[a][i]) - roc_auc_score(y[i], A[base][i]) for i in B]
    print(f"{a} − {base}：相关 {np.round(np.percentile(d1, [2.5, 97.5]), 3)}  DS AUC {np.round(np.percentile(d2, [2.5, 97.5]), 3)}")
# 合并：档案+Haiku 与 清单逐条平均 的秩平均（两次独立调用的平均）
from scipy.stats import rankdata
A["合并：档案+Haiku ⊕ 清单逐条"] = rankdata(A["档案+Haiku（现有）"]) + rankdata(A["区分清单 逐条平均"])
A["合并：档案+Haiku ⊕ 清单p_fail"] = rankdata(A["档案+Haiku（现有）"]) + rankdata(A["区分清单+Haiku p_fail"])
for k in ("合并：档案+Haiku ⊕ 清单逐条", "合并：档案+Haiku ⊕ 清单p_fail"):
    s, a, d = ev(A[k], I); d1 = [spearmanr(A[k][i], diff[i])[0] - spearmanr(A["档案+Haiku（现有）"][i], diff[i])[0] for i in B]
    print(f"{k} 相关 {s:+.3f} 14家AUC {a:.3f} DS AUC {d:.3f}  相关差区间 {np.round(np.percentile(d1, [2.5, 97.5]), 3)}")
