import json, hashlib, numpy as np, concurrent.futures as cf
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
import v4 as V
D = V.D
rid = lambda r: hashlib.md5((r["q"] + r["fail_side"] + r["pass_side"]).encode()).hexdigest()[:10]
SC = """判断下面这道新题在每条规则上更像「挂侧」还是「过侧」（0=明显像过侧，1=明显像挂侧，0.5=说不清）。只依据题面与动手前档案，不要使用对上游修法的记忆。
{rules}
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
只输出一行 JSON：{{"s":{{"规则编号":0~1,...}}}}"""
PR = open(__file__.replace("rule_loop_lib.py", "rule_loop.py")).read().split('PR = """')[1].split('"""')[0]
def score(task, rules, O):
    need = [r for r in rules if not (O.parent / "shared_scores" / rid(r) / f"{task}.json").exists()]
    if need:
        txt = "\n".join(f"{r['id']}. {r['q']}\n   挂侧：{r['fail_side']}\n   过侧：{r['pass_side']}" for r in need); res = None
        for _ in range(2):
            try: res = V.claude(SC.format(rules=txt, issue=D[task]["issue"][:6000], dos=V.DOS(task)), "claude-haiku-5-5", "s"); break
            except Exception: res = None
        if res:
            for r in need:
                v = res["s"].get(str(r["id"]), res["s"].get(r["id"]))
                if v is not None:
                    d = O.parent / "shared_scores" / rid(r); d.mkdir(parents=True, exist_ok=True); (d / f"{task}.json").write_text(json.dumps({"s": float(v)}))
    out = {}
    for r in rules:
        f = O.parent / "shared_scores" / rid(r) / f"{task}.json"; out[rid(r)] = json.load(open(f))["s"] if f.exists() else 0.5
    return out
def matrix(tasks, rules, O, jobs):
    with cf.ThreadPoolExecutor(jobs) as ex: rows = list(ex.map(lambda t: score(t, rules, O), tasks))
    return np.array([[row[rid(r)] for r in rules] for row in rows])
fit = lambda X, yy: LogisticRegression(C=0.5, max_iter=1000).fit(X, yy)
cvp = lambda X, yy: cross_val_predict(LogisticRegression(C=0.5, max_iter=1000), X, yy, cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba")[:, 1]
def propose(rules, w, X, p, yt, TRAIN):
    res = np.array([(p[i] - yt[i]) for i in range(len(TRAIN))]); order = np.argsort(res)
    fn = [i for i in order if yt[i] == 1][:6]; fp = [i for i in order[::-1] if yt[i] == 0][:6]; cases = ""
    for kind, idxs in (("漏报", fn), ("误报", fp)):
        for i in idxs:
            t = TRAIN[i]; at = V.AT.get(t); extra = f"\n阅卷：{str(at['L1_what'])[:500]}" if at and V.fail(t) else ""
            cases += f"\n--- [{kind}] 规则给 p={p[i]:.2f} ---\n题面：{D[t]['issue'][:1800]}\n档案：{V.DOS(t)[:2500]}\n规则打分：{ {r['id']: round(float(X[i][j]),2) for j, r in enumerate(rules)} }\n结果：DS {D[t]['passes']}/{D[t]['runs']} 次通过{extra}\n"
    rt = "\n".join(f"{r['id']}. {r['q']}（权重 {w[j]:+.2f}）｜挂侧：{r['fail_side']}｜过侧：{r['pass_side']}" for j, r in enumerate(rules))
    return V.claude(PR.format(n=len(fn) + len(fp), rules=rt, cases=cases), "claude-sonnet-5-5", "add")
