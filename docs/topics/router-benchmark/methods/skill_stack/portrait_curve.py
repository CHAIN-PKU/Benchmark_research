#!/usr/bin/env python3
"""几十道够不够（crc 20:58）：画像（区分清单）只用 n 对「挂/过」题归纳，不拟合任何权重（规则打分取平均），
在没用到的题上评 DS AUC；与同一批题上 Haiku 不看画像的 AUC 对比。n ∈ {6,12,24,40}，每个 n 抽 3 次。
用法：portrait_curve.py run [--jobs N]  输出 out_curve/"""
import sys, json, os, glob, hashlib, itertools
import numpy as np
from sklearn.metrics import roc_auc_score
import v4 as V
import contrast as C
import rule_loop_lib as L
ROOT = V.ROOT; D = V.D
O = ROOT / "out_curve"; O.mkdir(exist_ok=True); SH = ROOT / "out_kloop" / "shared" / "diff"
jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 6
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D)
JH = {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(str(ROOT / "out_judge_full/dos_haiku/*.json"))}
diffs = {}
for f in glob.glob(str(SH / "*.json")):
    t, u = os.path.basename(f)[:-5].split("__", 1) if "__" in os.path.basename(f)[:-5] else (None, None)
fails = sorted({os.path.basename(f)[:-5].split("__")[0] + "__" + os.path.basename(f)[:-5].split("__")[1] for f in glob.glob(str(SH / "*.json"))})
# 文件名是 <fail>__<pass>，任务 id 本身含 "__"（owner__repo-N），所以按已知任务集合拆
byfail = {}
for f in glob.glob(str(SH / "*.json")):
    n = os.path.basename(f)[:-5]
    for t in ALL:
        if n.startswith(t + "__") and n[len(t) + 2:] in ALL: byfail.setdefault(t, []).append((n[len(t) + 2:], f))
FAILS = sorted(byfail)
print(len(FAILS), "道挂题有成对对比缓存")
rows = []
for n in (6, 12, 24, 40):
    for rep in range(3):
        rng = np.random.default_rng(1000 * n + rep); pick = list(rng.permutation(FAILS)[: min(n, len(FAILS))])
        used = set(pick) | {byfail[t][0][0] for t in pick}; tag = f"n{n}_r{rep}"
        Rs = [json.load(open(byfail[t][0][1])) for t in pick]
        txt = "\n".join(f"--- 第{i+1}对 ---\n根本区别：{r['core']}\n" + "\n".join(f"· 挂侧：{d['fail_side']}｜过侧：{d['pass_side']}（{d.get('where','')}）" for d in r["diffs"]) for i, r in enumerate(Rs))
        ck = V.claude(C.CK.format(pairs=txt), "claude-sonnet-5-5", "items")["items"]
        rules = [{"id": i + 1, "q": c["question"], "fail_side": c["fail_side"], "pass_side": c["pass_side"]} for i, c in enumerate(ck)]
        test = [t for t in ALL if t not in used and t in JH]
        X = L.matrix(test, rules, O, jobs); s = X.mean(1); y = np.array([int(V.fail(t)) for t in test]); pb = np.array([JH[t] for t in test])
        rng2 = np.random.default_rng(0); B = [rng2.integers(0, len(test), len(test)) for _ in range(500)]
        a, b = roc_auc_score(y, s), roc_auc_score(y, pb)
        d = [roc_auc_score(y[i], s[i]) - roc_auc_score(y[i], pb[i]) for i in B if len(set(y[i])) == 2]
        rows.append(dict(n=n, rep=rep, n_rules=len(rules), n_test=len(test), test_fail=int(y.sum()), auc_portrait=a, auc_haiku=b, diff_ci=[float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]))
        print(f"n={n:2d} rep{rep} 规则{len(rules)}条 测试{len(test)}道（挂{int(y.sum())}）画像均分 AUC {a:.3f} | Haiku 不看画像 {b:.3f}", flush=True)
        json.dump(rows, open(O / "results.json", "w"), ensure_ascii=False, indent=1)
