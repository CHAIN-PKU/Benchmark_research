#!/usr/bin/env python3
"""挂/过成对对比（crc 11-16 18:19：不要只看挂题，要和没挂的题放一起比）。
  pairs           : 每折内给每道挂题配一道最像的过题（同仓库优先、坑类型构成最近、过题不重复用）→ out_con/pairs.json
  diff <模型>     : 并排读两份动手前档案 + 阅卷结论，问「动手前能看出的区别」→ out_con/diff/<挂题>.json   [Sonnet]
  checklist <模型>: 每折把各对区别汇总成区分清单（每条写清挂侧/过侧）→ out_con/checklist_fold<f>.json      [Sonnet]
  score <模型>    : 用另一折的清单给每道题逐条判「更像挂侧还是过侧」+ p_fail → out_con/score_<m>/<t>.json     [Haiku]"""
import sys, json, os, glob
import numpy as np
import v4 as V
ROOT = V.ROOT; S = V.S; D = V.D
FOLD = json.load(open(S / "refjudge/repo_fold.json"))
O = ROOT / "out_con"; O.mkdir(exist_ok=True)
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(str(ROOT / "out_pit/extract/*.json"))}
ALL = sorted(t for t in EXT if D[t]["repo"] in FOLD)
fold = lambda t: FOLD[D[t]["repo"]]
jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
vec = lambda t: np.array([sum(p["type"] == k for p in EXT[t]) for k in ("T1", "T2", "T3", "T4", "T5")])
DF = """下面是同一个编程智能体（DeepSeek）做过的两道真实仓库题。两道题的动手前档案里都列着类似的坑，但结果相反：A 挂了，B 两次都做对了。
请并排对比两份「动手前」档案（不要用事后才知道的信息当区别），找出动手前就能看出、可以解释「为什么 A 挂、B 没挂」的区别。
要求：每条区别必须是「A 是什么样、B 是什么样」的对照，不能是两边都有的坑；最多 3 条，按重要性排序。
只输出一行 JSON：{{"diffs":[{{"fail_side":"A 这一侧的特征（≤50字）","pass_side":"B 这一侧对应的样子（≤50字）","where":"在档案哪一节看得出"}}],"core":"一句话：A 挂 B 过的根本区别（≤60字）"}}

===== A（挂了，{ar}）：题面 =====
{ia}
===== A：动手前档案 =====
{da}
===== A：事后阅卷（只用来帮你定位 A 挂在哪，区别本身要从动手前档案里找）=====
{at}
===== B（做对了，{br}）：题面 =====
{ib}
===== B：动手前档案 =====
{db}"""
CK = """下面是编程智能体 DeepSeek 的若干「挂题 vs 最像的过题」成对对比，每对给出了动手前档案里能看出的区别。
请把它们归纳成一张「区分清单」：5~8 条，每条是一个能只看「题面 + 动手前档案」就回答的问题，并写清挂的一侧长什么样、过的一侧长什么样。
只保留在多对里反复出现的区别；两边都常见的坑不算区别。
只输出一行 JSON：{{"items":[{{"id":1,"question":"问题（≤40字）","fail_side":"挂侧（≤60字）","pass_side":"过侧（≤60字）","support":出现在几对里}}]}}

{pairs}"""
SC = """判断{agent}修好下面这道题、并通过维护者隐藏测试的可能性。不要使用对上游修法的记忆。
下面是从这个智能体的历史「挂题 vs 最像的过题」对比中总结的区分清单（来自其他仓库）。请对每一条，判断这道新题更像挂侧还是过侧（0=明显像过侧，1=明显像挂侧，0.5=说不清），再给整题失败概率。
{items}
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}

只输出一行 JSON：{{"per_item":[{{"id":1,"s":0~1}}],"p_fail":0~1,"reason":"一句话（≤60字）"}}"""
def items_text(f):
    C = json.load(open(O / f"checklist_fold{f}.json"))["items"]
    return "\n".join(f"{c['id']}. {c['question']}\n   挂侧：{c['fail_side']}\n   过侧：{c['pass_side']}" for c in C)
if __name__ == "__main__":
    step = sys.argv[1]
    if step == "pairs":
        P = {}
        for fo in set(FOLD.values()):
            fails = [t for t in ALL if fold(t) == fo and V.fail(t)]; used = set()
            for t in sorted(fails, key=lambda t: -int(t in V.AT)):
                cand = [u for u in ALL if fold(u) == fo and not V.fail(u) and u not in used]
                u = min(cand, key=lambda u: (D[u]["repo"] != D[t]["repo"], np.abs(vec(u) - vec(t)).sum(), abs(len(D[u]["issue"]) - len(D[t]["issue"]))))
                used.add(u); P[t] = u
        (O / "pairs.json").write_text(json.dumps(P, indent=1)); print(len(P), "pairs; same repo", sum(D[a]["repo"] == D[b]["repo"] for a, b in P.items()))
    elif step == "diff":
        model = sys.argv[2]; out = O / "diff"; out.mkdir(exist_ok=True); P = json.load(open(O / "pairs.json"))
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            u = P[t]; a = V.AT.get(t); at = f"{a['L1_what']}\n{a['L2_why']}"[:2500] if a else "（无阅卷记录）"
            try: r = V.claude(DF.format(ar=f"{D[t]['passes']}/{D[t]['runs']} 次通过", ia=D[t]["issue"][:3500], da=V.DOS(t), at=at, br=f"{D[u]['passes']}/{D[u]['runs']} 次通过", ib=D[u]["issue"][:3500], db=V.DOS(u)), model, "diffs")
            except Exception as e: return t, f"err {e}"
            r.update(fail=t, pass_=u); (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(sorted(P), f, jobs)
    elif step == "checklist":
        model = sys.argv[2]
        for fo in sorted(set(FOLD.values())):
            R = [json.load(open(p)) for p in glob.glob(str(O / "diff/*.json"))]
            R = [r for r in R if fold(r["fail"]) == fo]
            txt = "\n".join(f"--- 第{i+1}对 ---\n根本区别：{r['core']}\n" + "\n".join(f"· 挂侧：{d['fail_side']}｜过侧：{d['pass_side']}（{d.get('where','')}）" for d in r["diffs"]) for i, r in enumerate(R))
            c = V.claude(CK.format(pairs=txt), model, "items"); c["n_pairs"] = len(R)
            (O / f"checklist_fold{fo}.json").write_text(json.dumps(c, ensure_ascii=False, indent=1)); print(fo, len(R), "pairs ->", len(c["items"]), "items")
    elif step == "score":
        model = sys.argv[2]; short = model.replace("claude-", "").replace("-5-5", "")
        out = O / f"score_{short}"; out.mkdir(exist_ok=True)
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            other = [x for x in set(FOLD.values()) if x != fold(t)][0]
            try: r = V.claude(SC.format(agent=V.AGENT, items=items_text(other), issue=D[t]["issue"][:6000], dos=V.DOS(t)), model, "p_fail"); float(r["p_fail"])
            except Exception as e: return t, f"err {e}"
            r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(ALL, f, jobs)
