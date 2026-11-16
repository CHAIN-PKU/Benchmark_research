#!/usr/bin/env python3
"""让判断者「把训练折里所有做得出和做不出的题都读完」再判新题（模拟模型重新学习的过程，crc 01:02）。
casebook = 训练折（按仓库 5 折，不含被测题的仓库）里：全部 DS 挂的题 + 2 倍数量的 DS 做对的题（随机，固定种子），
每条：[挂/过 次数] 难点一句话 | 标准修复改了什么 | DS 做对/做错了什么 | 教训。不含被测题的任何信息。
用法：casebook_all.py run <模型> [--k 折] """
import sys, json, os, glob, random
import numpy as np
import v4 as V
ROOT = V.ROOT; D = V.D; model = sys.argv[2]; short = model.replace("claude-", "").replace("-5-5", "")
O = ROOT / f"out_casebook_{short}"; O.mkdir(exist_ok=True)
NOTE = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(str(ROOT / "out_note/*.json"))}
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D)
by = {}
for t in ALL: by.setdefault(D[t]["repo"], []).append(t)
FOLDS = [[] for _ in range(5)]; cnt = [0] * 5
for repo, ts in sorted(by.items(), key=lambda kv: -sum(V.fail(t) for t in kv[1]) * 100 - len(kv[1])):
    i = int(np.argmin(cnt)); FOLDS[i].append(repo); cnt[i] += sum(V.fail(t) for t in ts) + 0.3 * len(ts)
fold_of = {r: i for i, rs in enumerate(FOLDS) for r in rs}
def book(k):
    tr = [t for t in ALL if fold_of[D[t]["repo"]] != k and t in NOTE]; fl = [t for t in tr if V.fail(t)]; ps = [t for t in tr if not V.fail(t)]
    random.seed(1000 + k); ps = random.sample(ps, min(len(ps), 2 * len(fl))); L = fl + ps; random.seed(2000 + k); random.shuffle(L)
    lines = []
    for t in L:
        n = NOTE[t]; lines.append(f"[{'DS 挂' if V.fail(t) else 'DS 做对了'}，{D[t]['passes']}/{D[t]['runs']} 次通过] 难点：{V.core(t)[:110]} | 标准修复：{n['gold_changed'][:80]} | DS：{n['ds_outcome'][:80]} | 教训：{n['lesson'][:80]}")
    return "\n".join(f"{i+1}. {x}" for i, x in enumerate(lines)), len(fl), len(ps)
BOOK = {k: book(k) for k in range(5)}
for k in range(5): print("折", k, "casebook: 挂", BOOK[k][1], "过", BOOK[k][2], "字数", len(BOOK[k][0]))
ASK = "请先通读上面 DS 做过的所有题（做得出的和做不出的都要看），在心里对比归纳：DS 在什么样的题上做得出、什么样的题上做不出、两者的区别在哪里；然后把新题和这些题逐一对照，再给出失败概率。\n"
def f(t):
    if (O / f"{t}.json").exists(): return t, "skip"
    k = fold_of[D[t]["repo"]]
    cases = f"===== DS 在其他仓库做过的 {BOOK[k][1]+BOOK[k][2]} 道题：挂 {BOOK[k][1]} 道、做对 {BOOK[k][2]} 道（全部记录）=====\n{BOOK[k][0]}\n"
    try: r = V.claude(V.JUDGE.format(agent=V.AGENT, cases=cases, issue=D[t]["issue"][:6000], dos=V.DOS(t), ask=ASK), model, "p_fail"); float(r["p_fail"])
    except Exception as e: return t, f"err {e}"
    r["task"] = t; (O / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
sel = [t for t in ALL if (len(sys.argv) < 5 or fold_of[D[t]["repo"]] == int(sys.argv[4]))]
if "--smoke" in sys.argv: sel = sel[:2]
V.run(sel, f, 3)
