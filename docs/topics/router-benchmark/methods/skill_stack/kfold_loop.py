#!/usr/bin/env python3
"""5 折（按仓库分组）闭环：每次训练用约 80% 旧题，评剩下 20%（只评一次）。起始规则也只用训练题的挂/过成对对比得到。
用法：kfold_loop.py run <留出折 0-4> [--rounds 2] [--jobs 6]      输出 out_kloop/k<f>/"""
import sys, json, os, glob, hashlib, re
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict, StratifiedKFold
from sklearn.metrics import roc_auc_score
import v4 as V
import contrast as C   # 复用 DF/CK 提示；注意 contrast 的 ALL 依赖 out_pit/extract，这里不用
ROOT = V.ROOT; S = V.S; D = V.D
a = sys.argv; K = int(a[2]); R = int(a[a.index("--rounds") + 1]) if "--rounds" in a else 2; JOBS = int(a[a.index("--jobs") + 1]) if "--jobs" in a else 6
O = ROOT / "out_kloop" / f"k{K}"; (O / "scores").mkdir(parents=True, exist_ok=True); SH = ROOT / "out_kloop" / "shared"; (SH / "diff").mkdir(parents=True, exist_ok=True)
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D)
# 按仓库分 5 折，挂数均衡
by = {}
for t in ALL: by.setdefault(D[t]["repo"], []).append(t)
FOLDS = [[] for _ in range(5)]; cnt = [0] * 5
for repo, ts in sorted(by.items(), key=lambda kv: -sum(V.fail(t) for t in kv[1]) * 100 - len(kv[1])):
    i = int(np.argmin(cnt)); FOLDS[i].append(repo); cnt[i] += sum(V.fail(t) for t in ts) + 0.3 * len(ts)
fold_of = {repo: i for i, rs in enumerate(FOLDS) for repo in rs}
TEST = [t for t in ALL if fold_of[D[t]["repo"]] == K]; TRAIN = [t for t in ALL if fold_of[D[t]["repo"]] != K]
y = lambda L: np.array([int(V.fail(t)) for t in L]); yt = y(TRAIN)
rid = lambda r: hashlib.md5((r["q"] + r["fail_side"] + r["pass_side"]).encode()).hexdigest()[:10]
import rule_loop_lib as L  # 打分/拟合/改规则（从 rule_loop 抽出，不依赖折）
def main():
    # 1 起始规则：训练题内成对对比 → 区分清单
    vec = lambda t: np.zeros(1)
    fails = [t for t in TRAIN if V.fail(t)]; used = set(); pairs = {}
    for t in sorted(fails):
        cand = [u for u in TRAIN if not V.fail(u) and u not in used]
        u = min(cand, key=lambda u: (D[u]["repo"] != D[t]["repo"], abs(len(D[u]["issue"]) - len(D[t]["issue"])))); used.add(u); pairs[t] = u
    import concurrent.futures as cf
    def diff(t):
        u = pairs[t]; fn = SH / "diff" / f"{t}__{u}.json"
        if fn.exists(): return json.load(open(fn))
        at = V.AT.get(t); atx = f"{at['L1_what']}\n{at['L2_why']}"[:2500] if at else "（无阅卷记录）"
        r = V.claude(C.DF.format(ar=f"{D[t]['passes']}/{D[t]['runs']} 次通过", ia=D[t]["issue"][:3500], da=V.DOS(t), at=atx, br=f"{D[u]['passes']}/{D[u]['runs']} 次通过", ib=D[u]["issue"][:3500], db=V.DOS(u)), "claude-sonnet-5-5", "diffs")
        fn.write_text(json.dumps(r, ensure_ascii=False)); return r
    with cf.ThreadPoolExecutor(4) as ex: Rs = list(ex.map(diff, sorted(pairs)))
    txt = "\n".join(f"--- 第{i+1}对 ---\n根本区别：{r['core']}\n" + "\n".join(f"· 挂侧：{d['fail_side']}｜过侧：{d['pass_side']}（{d.get('where','')}）" for d in r["diffs"]) for i, r in enumerate(Rs))
    ck = V.claude(C.CK.format(pairs=txt), "claude-sonnet-5-5", "items")["items"]
    rules = [{"id": i + 1, "q": c["question"], "fail_side": c["fail_side"], "pass_side": c["pass_side"]} for i, c in enumerate(ck)]
    (O / "seed_checklist.json").write_text(json.dumps(rules, ensure_ascii=False, indent=1))
    log = []
    for k in range(R + 1):
        X = L.matrix(TRAIN, rules, O, JOBS); p = L.cvp(X, yt); m = L.fit(X, yt)
        ent = {"round": k, "n_rules": len(rules), "train_cv_auc": float(roc_auc_score(yt, p)), "train_cv_brier": float(np.mean((p - yt) ** 2)), "weights": [float(x) for x in m.coef_[0]]}
        print(f"k{K} 轮{k} 规则{len(rules)}条 训练内交叉验证 AUC {ent['train_cv_auc']:.3f} Brier {ent['train_cv_brier']:.4f}（常数 {yt.mean()*(1-yt.mean()):.4f}）", flush=True)
        (O / f"rules_r{k}.json").write_text(json.dumps({"rules": rules, "weights": ent["weights"]}, ensure_ascii=False, indent=1))
        if k == R: log.append(ent); break
        try: pr = L.propose(rules, m.coef_[0], X, p, yt, TRAIN)
        except Exception as e: print("propose err", e); log.append(ent); break
        ent["propose"] = pr; log.append(ent)
        keep = [r for r in rules if r["id"] not in set(pr.get("drop", []))]; nid = max(r["id"] for r in rules) + 1
        for c in pr.get("add", [])[:3]: keep.append({"id": nid, "q": c["q"], "fail_side": c["fail_side"], "pass_side": c["pass_side"]}); nid += 1
        rules = keep; print("  改规则：", pr.get("why", ""), "| 新增", len(pr.get("add", [])), "删除", pr.get("drop", []), flush=True)
    (O / "log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))
    for tag, rj in (("final", O / f"rules_r{R}.json"), ("seed", O / "rules_r0.json")):
        rr = json.load(open(rj))["rules"]; Xtr = L.matrix(TRAIN, rr, O, JOBS); mm = L.fit(Xtr, yt); Xte = L.matrix(TEST, rr, O, JOBS); pte = mm.predict_proba(Xte)[:, 1]
        (O / f"eval_{tag}.json").write_text(json.dumps({"tag": tag, "n_train": len(TRAIN), "train_fail": int(yt.sum()), "n_test": len(TEST), "const": float(yt.mean()), "p": {t: float(v) for t, v in zip(TEST, pte)}}, ensure_ascii=False))
        print(f"k{K} 留出[{tag}] n={len(TEST)}", flush=True)
if __name__ == "__main__": main()
