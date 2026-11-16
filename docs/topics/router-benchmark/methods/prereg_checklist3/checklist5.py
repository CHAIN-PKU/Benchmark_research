#!/usr/bin/env python3
"""奥卡姆版结构化清单（crc 22:10）：只保留在多轮、多折里反复出现的 5 条，每条只回答「触发 / 未触发」（0/1），
概率由 5 个二值特征的逻辑回归（训练折拟合）给出，不让 LLM 自己合成概率。
  tag <模型>：Haiku 对 186 题标 5 个 0/1 + 一句依据  → out_c5/<t>.json
  eval      ：5 折（按仓库）留出：清单回归 / 判断者校准 / 判断者 logit + 清单；输出每条的触发率与历史挂率"""
import sys, json, os, glob
import numpy as np
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_c5"; O.mkdir(exist_ok=True)
RULES = [
 ("R1", "期望行为没有明确定论", "题面没给确切的期望输出、异常类型、消息或接口形状，要靠推断（有复现与期望输出则为 0）"),
 ("R2", "没有可对照的现有测试，或与题面冲突", "档案里找不到能约束新行为的现有断言，或现有测试固化了与题面期望相反的行为"),
 ("R3", "题面自带误导线索", "题面的补丁、平台字样（如 on Windows）、链接或修法建议，可能把人带到错的位置或缩小范围"),
 ("R4", "只讲一侧，成对的另一侧可能也被测", "读/写、序列化/反序列化、TLS/非 TLS、开/关等成对情形，题面只提其中一侧"),
 ("R5", "修法需要按条件区分情形", "需要条件守卫或分支（不同类型、状态、平台走不同处理），而不是无条件改一处")]
P = """判断下面这道新题是否触发每条规则（1=触发，0=未触发）。只依据题面与动手前档案，不要使用对上游修法的记忆。保守：证据不足就判 0。
{rules}
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
只输出一行 JSON：{{"r1":0或1,"r2":0或1,"r3":0或1,"r4":0或1,"r5":0或1}}"""
if sys.argv[1] == "tag":
    model = sys.argv[2]; rt = "\n".join(f"{i} {n}：{d}" for i, n, d in RULES)
    ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D)
    def f(t):
        if (O / f"{t}.json").exists(): return t, "skip"
        try: r = V.claude(P.format(rules=rt, issue=D[t]["issue"][:6000], dos=V.DOS(t)), model, "r1"); assert all(k in r for k in ("r1", "r2", "r3", "r4", "r5"))
        except Exception as e: return t, f"err {e}"
        (O / f"{t}.json").write_text(json.dumps({k: int(r[k]) for k in ("r1", "r2", "r3", "r4", "r5")})); return t, "ok"
    V.run(ALL, f, 6)
if sys.argv[1] == "eval":
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from scipy.stats import spearmanr
    S = V.S; subs = [json.load(open(f)) for f in glob.glob(str(S / "pubhist/ml_*.json"))]
    ld = lambda d: {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(str(ROOT / d / "*.json"))}
    JH, JS = ld("out_judge_full/dos_haiku"), ld("out_judge_full/dos_sonnet")
    C5 = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(str(O / "*.json"))}
    ALL = sorted(t for t in C5 if t in D and t in JH and t in JS)
    by = {}
    for t in sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D): by.setdefault(D[t]["repo"], []).append(t)
    FOLDS = [[] for _ in range(5)]; cnt = [0] * 5
    for repo, ts in sorted(by.items(), key=lambda kv: -sum(V.fail(t) for t in kv[1]) * 100 - len(kv[1])):
        i = int(np.argmin(cnt)); FOLDS[i].append(repo); cnt[i] += sum(V.fail(t) for t in ts) + 0.3 * len(ts)
    fold = {r: i for i, rs in enumerate(FOLDS) for r in rs}
    y = np.array([int(V.fail(t)) for t in ALL]); fo = np.array([fold[D[t]["repo"]] for t in ALL]); X = np.array([[C5[t][k] for k in ("r1", "r2", "r3", "r4", "r5")] for t in ALL], float)
    lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
    print(f"n={len(ALL)} DS挂{y.sum()}\n规则  触发率  触发时挂率  未触发时挂率  与DS挂相关")
    for j, (i, n, _) in enumerate(RULES):
        m = X[:, j] == 1; print(f"{i} {n[:16]:16s} {m.mean():.0%}  {y[m].mean() if m.any() else float('nan'):.0%}({m.sum()})  {y[~m].mean():.0%}({(~m).sum()})  {spearmanr(X[:,j],y)[0]:+.2f}")
    def cv(feat):
        p = np.zeros(len(ALL))
        for k in range(5):
            tr, te = fo != k, fo == k; mdl = LogisticRegression(C=0.5, max_iter=2000).fit(feat[tr], y[tr]); p[te] = mdl.predict_proba(feat[te])[:, 1]
        return p
    const = np.array([y[fo != f].mean() for f in fo])
    arms = {"常数": const, "清单 5 条 → 回归": cv(X)}
    for n, J in (("Haiku", JH), ("Sonnet", JS)):
        lj = lg(np.array([J[t] for t in ALL]))[:, None]; arms[f"{n} 校准"] = cv(lj); arms[f"{n} 校准 + 清单"] = cv(np.c_[lj, X])
    pub = [i for i, t in enumerate(ALL) if all(t in s for s in subs)]; diff = np.array([np.mean([0 if s[ALL[i]]["resolved"] else 1 for s in subs]) for i in pub])
    rng = np.random.default_rng(0); B = [rng.integers(0, len(ALL), len(ALL)) for _ in range(2000)]
    auc = lambda p, i: roc_auc_score(y[i], p[i]) if len(set(y[i])) == 2 else np.nan
    for k, p in arms.items():
        ci = np.nanpercentile([auc(p, i) for i in B], [2.5, 97.5]); br = np.mean((p - y) ** 2); db = np.percentile([np.mean((p[i] - y[i]) ** 2) - np.mean((const[i] - y[i]) ** 2) for i in B], [2.5, 97.5])
        print(f"{k:16s} DS AUC {roc_auc_score(y,p) if k!='常数' else 0.5:.3f} [{ci[0]:.2f},{ci[1]:.2f}] | Brier {br:.4f} (比常数 {br-np.mean((const-y)**2):+.4f} 区间 {np.round(db,3)}) | 与难度相关 {spearmanr(np.array(p)[pub],diff)[0]:+.3f}")
    for n in ("Haiku", "Sonnet"):
        d = [auc(arms[f"{n} 校准 + 清单"], i) - auc(arms[f"{n} 校准"], i) for i in B]; db = [np.mean((arms[f"{n} 校准 + 清单"][i] - y[i]) ** 2) - np.mean((arms[f"{n} 校准"][i] - y[i]) ** 2) for i in B]
        print(f"{n}: 加清单 − 只校准  DS AUC 区间 {np.round(np.nanpercentile(d,[2.5,97.5]),3)} | Brier 区间 {np.round(np.percentile(db,[2.5,97.5]),4)}")
