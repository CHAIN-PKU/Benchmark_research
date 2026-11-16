#!/usr/bin/env python3
"""闭环：规则 → 打分 → 找出判错的训练题 → Sonnet 归因并改规则 → 再打分，迭代 R 轮。只用 DS 成败；留出折只在最后评一次。
用法：rule_loop.py run <训练折 0|1> [--rounds 3] [--jobs 6]
输出 out_loop/fold<f>/：rules_r<k>.json、scores/<hash>/<task>.json、log.json、final_eval.json"""
import sys, json, os, glob, hashlib, re, subprocess
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.metrics import roc_auc_score
import v4 as V
ROOT = V.ROOT; S = V.S; D = V.D
FO = json.load(open(S / "refjudge/repo_fold.json")); fold = lambda t: FO[D[t]["repo"]]
a = sys.argv; TR = int(a[2]); R = int(a[a.index("--rounds") + 1]) if "--rounds" in a else 3; JOBS = int(a[a.index("--jobs") + 1]) if "--jobs" in a else 6
O = ROOT / "out_loop" / f"fold{TR}"; (O / "scores").mkdir(parents=True, exist_ok=True)
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D and D[os.path.basename(f)[:-3]]["repo"] in FO)
TRAIN = [t for t in ALL if fold(t) == TR]; TEST = [t for t in ALL if fold(t) != TR]
y = lambda L: np.array([int(V.fail(t)) for t in L])
rid = lambda r: hashlib.md5((r["q"] + r["fail_side"] + r["pass_side"]).encode()).hexdigest()[:10]
SC = """判断下面这道新题在每条规则上更像「挂侧」还是「过侧」（0=明显像过侧，1=明显像挂侧，0.5=说不清）。只依据题面与动手前档案，不要使用对上游修法的记忆。
{rules}
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
只输出一行 JSON：{{"s":{{"规则编号":0~1,...}}}}"""
def score(task, rules):
    out = {}
    need = [r for r in rules if not (O / "scores" / rid(r) / f"{task}.json").exists()]
    if need:
        txt = "\n".join(f"{r['id']}. {r['q']}\n   挂侧：{r['fail_side']}\n   过侧：{r['pass_side']}" for r in need)
        for _ in range(2):
            try:
                res = V.claude(SC.format(rules=txt, issue=D[task]["issue"][:6000], dos=V.DOS(task)), "claude-haiku-5-5", "s"); break
            except Exception: res = None
        if res:
            for r in need:
                v = res["s"].get(str(r["id"]), res["s"].get(r["id"]))
                if v is not None:
                    d = O / "scores" / rid(r); d.mkdir(exist_ok=True); (d / f"{task}.json").write_text(json.dumps({"s": float(v)}))
    for r in rules:
        f = O / "scores" / rid(r) / f"{task}.json"
        out[rid(r)] = json.load(open(f))["s"] if f.exists() else 0.5
    return out
def matrix(tasks, rules):
    import concurrent.futures as cf
    with cf.ThreadPoolExecutor(JOBS) as ex: rows = list(ex.map(lambda t: score(t, rules), tasks))
    return np.array([[row[rid(r)] for r in rules] for row in rows])
def fit(X, yy): return LogisticRegression(C=0.5, class_weight=None, max_iter=1000).fit(X, yy)
def cvp(X, yy): return cross_val_predict(LogisticRegression(C=0.5, max_iter=1000), X, yy, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
PR = """你在改进一组「动手前判断规则」。规则是一个能只看「题面 + 动手前仓库档案」回答的问题，用来预测编程智能体 DeepSeek 做这道题会不会挂；每条规则的权重由训练题的真实成败拟合。
下面是当前规则（含权重，正=越像挂侧越会挂），以及 {n} 道「当前规则判错」的训练题：漏报（实际挂了，规则却判低）和误报（实际做对，规则却判高），每题附事后结果与规则打分。
请找出这些判错题的共性，修改规则集：新增 ≤3 条（必须能只看题面+档案回答，要能把「漏报题」与「相似的做对的题」区分开，写清挂侧/过侧），删除或改写 ≤2 条（无用或误导的）。
只输出一行 JSON：{{"add":[{{"q":"问题（≤40字）","fail_side":"挂侧（≤60字）","pass_side":"过侧（≤60字）"}}],"drop":[规则编号],"why":"一句话（≤80字）"}}

===== 当前规则 =====
{rules}
===== 判错的训练题 =====
{cases}"""
def propose(rules, w, X, p, yt):
    res = np.array([(p[i] - yt[i]) for i in range(len(TRAIN))]); order = np.argsort(res)
    fn = [i for i in order if yt[i] == 1][:6]; fp = [i for i in order[::-1] if yt[i] == 0][:6]
    cases = ""
    for kind, idxs in (("漏报", fn), ("误报", fp)):
        for i in idxs:
            t = TRAIN[i]; at = V.AT.get(t); extra = f"\n阅卷：{str(at['L1_what'])[:500]}" if at and V.fail(t) else ""
            cases += f"\n--- [{kind}] 规则给 p={p[i]:.2f} ---\n题面：{D[t]['issue'][:1800]}\n档案：{V.DOS(t)[:2500]}\n规则打分：{ {r['id']: round(float(X[i][j]),2) for j, r in enumerate(rules)} }\n结果：DS {D[t]['passes']}/{D[t]['runs']} 次通过{extra}\n"
    rt = "\n".join(f"{r['id']}. {r['q']}（权重 {w[j]:+.2f}）｜挂侧：{r['fail_side']}｜过侧：{r['pass_side']}" for j, r in enumerate(rules))
    return V.claude(PR.format(n=len(fn) + len(fp), rules=rt, cases=cases), "claude-sonnet-5-5", "add")
def main():
    ck = json.load(open(ROOT / "out_con" / f"checklist_fold{TR}.json"))["items"]
    rules = [{"id": i + 1, "q": c["question"], "fail_side": c["fail_side"], "pass_side": c["pass_side"]} for i, c in enumerate(ck)]
    log = []; yt = y(TRAIN)
    for k in range(R + 1):
        X = matrix(TRAIN, rules); p = cvp(X, yt); m = fit(X, yt)
        ent = {"round": k, "n_rules": len(rules), "train_cv_auc": float(roc_auc_score(yt, p)), "train_cv_brier": float(np.mean((p - yt) ** 2)), "weights": [float(x) for x in m.coef_[0]]}
        print(f"轮{k} 规则{len(rules)}条 训练折交叉验证 AUC {ent['train_cv_auc']:.3f} Brier {ent['train_cv_brier']:.4f}（常数 {yt.mean()*(1-yt.mean()):.4f}）", flush=True)
        (O / f"rules_r{k}.json").write_text(json.dumps({"rules": rules, "weights": ent["weights"]}, ensure_ascii=False, indent=1))
        if k == R: log.append(ent); break
        try: pr = propose(rules, m.coef_[0], X, p, yt)
        except Exception as e: print("propose err", e); log.append(ent); break
        ent["propose"] = pr; log.append(ent)
        keep = [r for r in rules if r["id"] not in set(pr.get("drop", []))]; nid = max(r["id"] for r in rules) + 1
        for c in pr.get("add", [])[:3]: keep.append({"id": nid, "q": c["q"], "fail_side": c["fail_side"], "pass_side": c["pass_side"]}); nid += 1
        rules = keep; print("  改规则：", pr.get("why", ""), "| 新增", len(pr.get("add", [])), "删除", pr.get("drop", []), flush=True)
    (O / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))
    # 留出折：只评一次，用最终规则 + 全训练折拟合的权重；同时评第 0 轮规则作对照
    for tag, rj in (("final", O / f"rules_r{R}.json"), ("seed", O / "rules_r0.json")):
        rr = json.load(open(rj))["rules"]; Xtr = matrix(TRAIN, rr); mm = fit(Xtr, yt); Xte = matrix(TEST, rr); pte = mm.predict_proba(Xte)[:, 1]; yte = y(TEST)
        const = np.full(len(TEST), yt.mean())
        subs = [json.load(open(f)) for f in glob.glob(str(S / "pubhist/ml_*.json"))]; pub = [i for i, t in enumerate(TEST) if all(t in s for s in subs)]
        from scipy.stats import spearmanr
        diff = np.array([np.mean([0 if s[TEST[i]]["resolved"] else 1 for s in subs]) for i in pub])
        ev = {"tag": tag, "n_rules": len(rr), "n_test": len(TEST), "test_fail": int(yte.sum()), "auc_ds": float(roc_auc_score(yte, pte)), "brier": float(np.mean((pte - yte) ** 2)), "brier_const": float(np.mean((const - yte) ** 2)),
              "spearman_public": float(spearmanr(pte[pub], diff)[0]), "p": {t: float(v) for t, v in zip(TEST, pte)}}
        (O / f"eval_{tag}.json").write_text(json.dumps(ev, ensure_ascii=False)); print(f"留出折[{tag}] AUC {ev['auc_ds']:.3f} Brier {ev['brier']:.4f}（常数 {ev['brier_const']:.4f}） 与公开难度相关 {ev['spearman_public']:+.3f}", flush=True)
if __name__ == "__main__": main()
