"""方法 1：叠加校准。在 186 道训练题上做交叉验证（随机分层 5 折×10 次，以及按仓库分组 5 折），
比较各单项信息与合成分数的 AUC/Brier。所有特征都只用事前信息（除「理想知识点」上限参照）。"""
import json, glob, re, sys, math, numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, GroupKFold
from sklearn.metrics import roc_auc_score, brier_score_loss
S = sys.argv[1]; T = S + "/tagging"
d = json.load(open(T + "/tag_data.json"))
P = {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(S + "/train_tags/out/sonnet_tags/*.json")}
A = {json.load(open(f))["task"]: json.load(open(f))["units"] for f in glob.glob(T + "/out/fx_sonnet/*.json")}
B = {json.load(open(f))["task"]: json.load(open(f))["units"] for f in glob.glob(T + "/out/fx_opus/*.json")}
ts = sorted(t for t in P if t in A and t in B and t in d)
U = [f"R{i:02d}" for i in range(1, 19)]
y = np.array([int(d[t]["passes"] < d[t]["runs"]) for t in ts])
repo = np.array([d[t]["repo"] for t in ts])
issue = [open(f"{S}/train_tags/issue/{t}.md").read() for t in ts]
llm = np.array([float(P[t]["p_fail"]) for t in ts])
upre = np.array([[int(P[t]["units"].get(u, 0)) for u in U] for t in ts])
uora = np.array([[int(int(A[t].get(u, 0)) and int(B[t].get(u, 0))) for u in U] for t in ts])
simple = np.array([[math.log1p(len(x)), len(re.findall(r"[\w/]+\.\w{1,4}\b", x)), x.count("```")] for x in issue])
print("n", len(ts), "fails", y.sum())

def fold_feats(tr, te):
    vec = TfidfVectorizer(min_df=2, sublinear_tf=True).fit([issue[i] for i in tr])
    Xtr, Xte = vec.transform([issue[i] for i in tr]), vec.transform([issue[i] for i in te])
    sim = (Xte @ Xtr.T).toarray()
    k = 10; nn = np.argsort(-sim, axis=1)[:, :k]
    knn_te = y[tr][nn].mean(1)
    simtr = (Xtr @ Xtr.T).toarray(); np.fill_diagonal(simtr, -1)
    knn_tr = y[tr][np.argsort(-simtr, axis=1)[:, :k]].mean(1)
    prior = y[tr].mean()
    def rp(idx):
        out = []
        for i in idx:
            m = [j for j in tr if repo[j] == repo[i] and j != i]
            out.append((y[m].sum() + 2 * prior) / (len(m) + 2))
        return np.array(out)
    return knn_tr, knn_te, rp(tr), rp(te)

def lr_fit_pred(Xtr, ytr, Xte, C=1.0):
    m = LogisticRegression(C=C, max_iter=2000).fit(Xtr, ytr); return m.predict_proba(Xte)[:, 1]

def run(splitter, groups=None, reps=1):
    names = ["llm", "knn", "repo_prior", "simple", "units_pre", "units_oracle(上限)", "stack(llm+knn+units_pre+simple)", "stack(llm+knn)"]
    agg = {n: [] for n in names}; br = {n: [] for n in names}
    for r in range(reps):
        sp = splitter(r)
        oof = {n: np.zeros(len(ts)) for n in names}
        it = sp.split(np.zeros(len(ts)), y, groups) if groups is not None else sp.split(np.zeros(len(ts)), y)
        for tr, te in it:
            knn_tr, knn_te, rp_tr, rp_te = fold_feats(tr, te)
            oof["llm"][te] = llm[te]; oof["knn"][te] = knn_te; oof["repo_prior"][te] = rp_te
            oof["simple"][te] = lr_fit_pred(simple[tr], y[tr], simple[te])
            oof["units_pre"][te] = lr_fit_pred(upre[tr], y[tr], upre[te], C=0.3)
            oof["units_oracle(上限)"][te] = lr_fit_pred(uora[tr], y[tr], uora[te], C=0.3)
            # 叠加：内层用训练折的 out-of-fold 单项分数训练合成器，避免泄漏
            inner_units = np.zeros(len(tr)); inner_simple = np.zeros(len(tr))
            for itr, ite in StratifiedKFold(5, shuffle=True, random_state=r).split(np.zeros(len(tr)), y[tr]):
                inner_units[ite] = lr_fit_pred(upre[tr][itr], y[tr][itr], upre[tr][ite], C=0.3)
                inner_simple[ite] = lr_fit_pred(simple[tr][itr], y[tr][itr], simple[tr][ite])
            te_units = lr_fit_pred(upre[tr], y[tr], upre[te], C=0.3); te_simple = lr_fit_pred(simple[tr], y[tr], simple[te])
            Ztr = np.c_[llm[tr], knn_tr, inner_units, inner_simple]; Zte = np.c_[llm[te], knn_te, te_units, te_simple]
            oof["stack(llm+knn+units_pre+simple)"][te] = lr_fit_pred(Ztr, y[tr], Zte)
            oof["stack(llm+knn)"][te] = lr_fit_pred(Ztr[:, :2], y[tr], Zte[:, :2])
        for n in names:
            agg[n].append(roc_auc_score(y, oof[n])); br[n].append(brier_score_loss(y, np.clip(oof[n], 0, 1)))
    for n in names:
        print(f"  {n:34s} AUC {np.mean(agg[n]):.3f} (±{np.std(agg[n]):.3f})  Brier {np.mean(br[n]):.3f}")

print("== 随机分层 5 折 × 10 次"); run(lambda r: StratifiedKFold(5, shuffle=True, random_state=r), reps=10)
print("== 按仓库分组 5 折（换仓库）"); run(lambda r: GroupKFold(5), groups=repo, reps=1)
print("基准 Brier（全猜均值）", round(float(np.mean((y - y.mean()) ** 2)), 3))
