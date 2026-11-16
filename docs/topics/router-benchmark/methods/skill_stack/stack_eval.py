#!/usr/bin/env python3
"""5 折（按仓库）留出：统计模型在训练折上拟合，留出折只评一次。
 臂：常数 | 判断者原始 p（Haiku/Sonnet） | 技能 Q 向量→回归 | Q + 判断者 logit（逐判断者的修正） | 5 折规则打分（seed 规则）| 规则 + 判断者
评价：DS AUC（带 bootstrap 区间）、Brier（相对常数）、与 14 家难度相关。"""
import json, glob, os, sys, numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
R = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(R)
D = json.load(open(f"{S}/tagging/tag_data.json")); subs = [json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
tax = json.load(open(f"{R}/out_tax/taxonomy.json"))["skills"]; ids = [s["id"] for s in tax]
Q = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(f"{R}/out_tax/q/*.json")}
ld = lambda d: {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(f"{R}/{d}/*.json")}
JH, JS = ld("out_judge_full/dos_haiku"), ld("out_judge_full/dos_sonnet")
# 折：与 kfold_loop 同一划分（复制其逻辑）
import v4 as V
ALL = sorted(t for t in Q if t in D and t in JH and t in JS)
by = {}
for t in sorted(os.path.basename(f)[:-3] for f in glob.glob(f"{R}/out_dossier/*.md") if os.path.basename(f)[:-3] in D): by.setdefault(D[t]["repo"], []).append(t)
FOLDS = [[] for _ in range(5)]; cnt = [0] * 5
for repo, ts in sorted(by.items(), key=lambda kv: -sum(V.fail(t) for t in kv[1]) * 100 - len(kv[1])):
    i = int(np.argmin(cnt)); FOLDS[i].append(repo); cnt[i] += sum(V.fail(t) for t in ts) + 0.3 * len(ts)
fold = {repo: i for i, rs in enumerate(FOLDS) for repo in rs}
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
y = np.array([int(V.fail(t)) for t in ALL]); fo = np.array([fold[D[t]["repo"]] for t in ALL])
XQ = np.array([[Q[t][i] for i in ids] for t in ALL])
def kloop_p(tag):  # 规则打分臂：来自 kfold_loop 的留出预测
    P = {}
    for k in range(5):
        f = f"{R}/out_kloop/k{k}/eval_{tag}.json"
        if os.path.exists(f): P.update(json.load(open(f))["p"])
    return P
RS = kloop_p("seed")
def cv(make):
    p = np.zeros(len(ALL))
    for k in range(5):
        tr, te = fo != k, fo == k; X = make(); m = LogisticRegression(C=0.3, max_iter=2000).fit(X[tr], y[tr]); p[te] = m.predict_proba(X[te])[:, 1]
    return p
const = np.array([y[fo != f].mean() for f in fo])
arms = {"常数（历史通过率）": const}
for n, J in (("Haiku", JH), ("Sonnet", JS)):
    lj = lg(np.array([J[t] for t in ALL]))[:, None]
    arms[f"{n} 原始 p（未校准）"] = np.array([J[t] for t in ALL])
    arms[f"{n} p 经训练折校准（Platt）"] = cv(lambda: lj)
    arms[f"{n} + 技能 Q 向量（逐判断者修正）"] = cv(lambda: np.c_[lj, XQ])
arms["技能 Q 向量 → 回归（无判断者）"] = cv(lambda: XQ)
if len(RS) >= len(ALL) - 5:
    ts_ok = [t in RS for t in ALL]; arms["5折规则打分（挂过对比规则）"] = np.array([RS.get(t, np.nan) for t in ALL])
ok = np.array([all(not np.isnan(v[i]) for v in arms.values()) for i in range(len(ALL))])
pub = np.array([all(t in s for s in subs) for t in ALL]) & ok
diff = np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) if all(t in s for s in subs) else np.nan for t in ALL])
rng = np.random.default_rng(0); B = [rng.integers(0, len(ALL), len(ALL)) for _ in range(2000)]
auc = lambda p, i: roc_auc_score(y[i], p[i]) if len(set(y[i])) == 2 else np.nan
print(f"n={ok.sum()} DS挂{y[ok].sum()} 常数Brier {np.mean((const[ok]-y[ok])**2):.4f}")
for k, p in arms.items():
    ci = np.nanpercentile([auc(p, i) for i in B], [2.5, 97.5]); br = np.mean((p[ok] - y[ok]) ** 2)
    db = np.percentile([np.mean((p[i] - y[i]) ** 2) - np.mean((const[i] - y[i]) ** 2) for i in B], [2.5, 97.5])
    print(f"{k:34s} DS AUC {roc_auc_score(y[ok],p[ok]):.3f} [{ci[0]:.2f},{ci[1]:.2f}] | Brier {br:.4f} (比常数 {br-np.mean((const[ok]-y[ok])**2):+.4f} 区间 {np.round(db,3)}) | 与难度相关 {spearmanr(p[pub],diff[pub])[0]:+.3f}")
for n in ("Haiku", "Sonnet"):
    for b in (f"{n} 原始 p（未校准）", f"{n} p 经训练折校准（Platt）"):
        a = f"{n} + 技能 Q 向量（逐判断者修正）"; d = [auc(arms[a], i) - auc(arms[b], i) for i in B]; print(f"  {a} − {b}: DS AUC 区间 {np.round(np.nanpercentile(d,[2.5,97.5]),3)}")
# 技能项各自与成败 / 与判断者 p 的关系（牵引 vs 预示）
print("\n技能项  名称            与DS挂的相关  与Haiku p相关  与Sonnet p相关")
for j, s in enumerate(tax):
    print(f"{s['id']:4s} {s['name']:12s}  {spearmanr(XQ[:,j],y)[0]:+.2f}        {spearmanr(XQ[:,j],[JH[t] for t in ALL])[0]:+.2f}         {spearmanr(XQ[:,j],[JS[t] for t in ALL])[0]:+.2f}")

# 稀疏修正：训练折内按「与成败相关」选前 m 个技能项（只看训练折），再与判断者 logit 一起回归
def cv_sel(lj, m, C=0.3):
    p = np.zeros(len(ALL))
    for k in range(5):
        tr, te = fo != k, fo == k
        sc = [abs(spearmanr(XQ[tr, j], y[tr])[0]) for j in range(XQ.shape[1])]; top = np.argsort(sc)[::-1][:m]
        X = np.c_[lj, XQ[:, top]]; mdl = LogisticRegression(C=C, max_iter=2000).fit(X[tr], y[tr]); p[te] = mdl.predict_proba(X[te])[:, 1]
    return p
print("\n稀疏修正（训练折内选前 m 项技能 + 判断者 logit）")
for n, J in (("Haiku", JH), ("Sonnet", JS)):
    lj = lg(np.array([J[t] for t in ALL]))[:, None]; base = arms[f"{n} p 经训练折校准（Platt）"]
    for m in (2, 3, 5):
        p = cv_sel(lj, m); d = [auc(p, i) - auc(base, i) for i in B]; db = np.percentile([np.mean((p[i]-y[i])**2) - np.mean((base[i]-y[i])**2) for i in B], [2.5, 97.5])
        print(f"{n} + 前{m}项: DS AUC {roc_auc_score(y,p):.3f}（Platt 校准 {roc_auc_score(y,base):.3f}） 差区间 {np.round(np.nanpercentile(d,[2.5,97.5]),3)} | Brier {np.mean((p-y)**2):.4f} vs {np.mean((base-y)**2):.4f} 差区间 {np.round(db,4)}")
