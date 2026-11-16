#!/usr/bin/env python3
"""分解预测器评估：p = 1 − ∏_i (1 − h_i · m_类型)，h_i = 3 份模拟测试里覆盖该坑的票数/3，m_类型 = 训练折里 DS 对「被考到的该类坑」的失手率（按仓库 5 折）。
同时报：①坑级「被考到」预测的 AUC（914 坑，验证模拟测试）；②整题对 DS 成败的 AUC/Brier；③一致度（欠规范）单独作为信号；④与判断者的组合。"""
import json, glob, os, numpy as np, sys
sys.argv = ["x", "run"]
import v4 as V
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from scipy.stats import spearmanr
ROOT = V.ROOT; D = V.D; O = ROOT / "out_ts"
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(str(ROOT / "out_pit/extract/*.json"))}
HIT = {os.path.basename(f)[:-5]: json.load(open(f))["hit"] for f in glob.glob(str(ROOT / "out_hit/*.json"))}
VOTE = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(str(O / "vote/*.json"))}
FELL = {os.path.basename(f)[:-5]: set(json.load(open(f)).get("fell", [])) for f in glob.glob(str(ROOT / "out_pit/label/*.json"))}
CONS = {os.path.basename(f)[:-5]: float(json.load(open(f))["agree"]) for f in glob.glob(str(O / "cons/*.json"))}
CMP = {os.path.basename(f)[:-5]: np.mean(json.load(open(f))["covered"]) for f in glob.glob(str(O / "cmp/*.json"))}
ld = lambda d: {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(str(ROOT / d / "*.json"))}
JS = ld("out_judge_full/dos_sonnet"); JH = ld("out_judge_full/dos_haiku")
ts = sorted(t for t in VOTE if t in D and t in CONS and t in CMP and t in JS and t in JH and t in HIT)
y = np.array([int(V.fail(t)) for t in ts])
FO = json.load(open(V.S / "refjudge/repo_fold.json")); by = {}
for t in sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D): by.setdefault(D[t]["repo"], []).append(t)
FOLDS = [[] for _ in range(5)]; cnt = [0] * 5
for repo, tt in sorted(by.items(), key=lambda kv: -sum(V.fail(t) for t in kv[1]) * 100 - len(kv[1])):
    i = int(np.argmin(cnt)); FOLDS[i].append(repo); cnt[i] += sum(V.fail(t) for t in tt) + 0.3 * len(tt)
fold = {r: i for i, rs in enumerate(FOLDS) for r in rs}; fo = np.array([fold[D[t]["repo"]] for t in ts])
# ① 坑级验证
hv = [(VOTE[t].get(str(p["id"]), 0) / 3, HIT[t].get(str(p["id"]), 0), p["type"]) for t in ts for p in EXT[t]]
x = np.array([a for a, _, _ in hv]); h = np.array([b for _, b, _ in hv])
print(f"① 模拟测试预测「坑被隐藏测试考到」：{len(hv)} 个坑，AUC {roc_auc_score(h, x):.3f}（类型先验 0.568、仓库先验 0.521）；票数 0/1/2/3 的被考到比例：", {k: f"{h[x*3==k].mean():.0%}({(x*3==k).sum()})" for k in (0, 1, 2, 3)})
# ② 整题
def mrates(tr_tasks):
    cnt = {}
    for t in tr_tasks:
        for p in EXT[t]:
            if HIT[t].get(str(p["id"]), 0): c = cnt.setdefault(p["type"], [0, 0]); c[1] += 1; c[0] += int(p["id"] in FELL.get(t, set()) if V.fail(t) else 0)
    allm = sum(c[0] for c in cnt.values()) / max(1, sum(c[1] for c in cnt.values()))
    return {k: (c[0] + 2 * allm) / (c[1] + 2) for k, c in cnt.items()}, allm
def predict(t, m, allm, oracle=False):
    q = 1.0
    for p in EXT[t]:
        hi = (HIT[t].get(str(p["id"]), 0) if oracle else VOTE[t].get(str(p["id"]), 0) / 3); q *= 1 - hi * m.get(p["type"], allm)
    return 1 - q
pd = np.zeros(len(ts)); po = np.zeros(len(ts))
for k in range(5):
    tr = [t for t, f in zip(ts, fo) if f != k]; m, allm = mrates(tr)
    for i, (t, f) in enumerate(zip(ts, fo)):
        if f == k: pd[i] = predict(t, m, allm); po[i] = predict(t, m, allm, oracle=True)
const = np.array([y[fo != f].mean() for f in fo]); lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
def cv(F):
    p = np.zeros(len(ts))
    for k in range(5): tr, te = fo != k, fo == k; p[te] = LogisticRegression(C=0.5, max_iter=2000).fit(F[tr], y[tr]).predict_proba(F[te])[:, 1]
    return p
cons = np.array([CONS[t] for t in ts]); cmpv = np.array([CMP[t] for t in ts]); ljs = lg(np.array([JS[t] for t in ts]))[:, None]; ljh = lg(np.array([JH[t] for t in ts]))[:, None]
arms = {"常数": const, "分解预测器（模拟测试票数 × DS 各类失手率）": pd, "分解预测器·上帝视角（用真实被考到）": po, "一致度（欠规范）→回归": cv((1 - cons)[:, None]), "模拟测试对真实测试覆盖度（仅验证用）→回归": cv((1 - cmpv)[:, None]),
        "Sonnet 校准": cv(ljs), "Sonnet + 一致度": cv(np.c_[ljs, 1 - cons]), "Sonnet + 分解预测器": cv(np.c_[ljs, lg(pd)[:, None]]), "Haiku 校准": cv(ljh), "Haiku + 一致度": cv(np.c_[ljh, 1 - cons]), "Haiku + 分解预测器": cv(np.c_[ljh, lg(pd)[:, None]])}
rng = np.random.default_rng(0); B = [rng.integers(0, len(ts), len(ts)) for _ in range(2000)]; au = lambda p, i: roc_auc_score(y[i], p[i]) if len(set(y[i])) == 2 else np.nan
print(f"\n② 整题（n={len(ts)}，DS 挂 {y.sum()}，按仓库 5 折留出）")
for k, p in arms.items():
    ci = np.nanpercentile([au(p, i) for i in B], [2.5, 97.5]); br = np.mean((p - y) ** 2); db = np.percentile([np.mean((p[i] - y[i]) ** 2) - np.mean((const[i] - y[i]) ** 2) for i in B], [2.5, 97.5])
    print(f"{k:34s} DS AUC {roc_auc_score(y,p) if k!='常数' else 0.5:.3f} [{ci[0]:.2f},{ci[1]:.2f}] | Brier {br:.4f} (比常数 {br-np.mean((const-y)**2):+.4f} 区间 {np.round(db,3)})")
for n in ("Sonnet", "Haiku"):
    for extra in ("一致度", "分解预测器"):
        d = [au(arms[f"{n} + {extra}"], i) - au(arms[f"{n} 校准"], i) for i in B]; print(f"{n}: 加 {extra} − 只校准  DS AUC 区间 {np.round(np.nanpercentile(d,[2.5,97.5]),3)}")
print(f"\n③ 一致度与 DS 成败的相关 {spearmanr(cons,y)[0]:+.2f}；覆盖度与 DS 成败的相关 {spearmanr(cmpv,y)[0]:+.2f}；一致度与覆盖度的相关 {spearmanr(cons,cmpv)[0]:+.2f}")
