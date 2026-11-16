#!/usr/bin/env python3
"""方法 v4 扩样本：所有有档案的旧题都当目标题；案例只从另一折仓库里挑（repo_fold.json）。
步骤同 v4.py：note（全部题写事后注记）/ select（每题从另一折挑 2 挂 2 过）/ judge <dos|case> <模型>。
输出目录加后缀 _full，不覆盖小样结果。"""
import sys, json, pathlib, glob, os
sys.argv = [sys.argv[0]] + sys.argv[1:]
import v4 as V
ROOT = V.ROOT; S = V.S; D = V.D
FOLD = json.load(open(S / "refjudge/repo_fold.json"))
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D)
fold = lambda t: FOLD[D[t]["repo"]]
step = sys.argv[1]; jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
if step == "note":
    model = sys.argv[2]; out = ROOT / "out_note"; out.mkdir(exist_ok=True)
    def f(t):
        if (out / f"{t}.json").exists(): return t, "skip"
        a = V.AT.get(t); attr = f"\n【阅卷归因】{a['L1_what']}；{a['L2_why']}" if a and V.fail(t) else ""
        try:
            r = V.claude(V.NOTE.format(dos=V.DOS(t)[:3000], gold=D[t].get("gold", "")[:3000], res=f"{D[t]['passes']}/{D[t]['runs']} 次通过", attr=attr), model, "lesson")
        except Exception as e:
            return t, f"err {e}"
        (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
    V.run(ALL, f, jobs)
elif step == "select":
    model = sys.argv[2]; out = ROOT / "out_sel_full"; out.mkdir(exist_ok=True)
    def f(t):
        if (out / f"{t}.json").exists(): return t, "skip"
        pool = [o for o in ALL if fold(o) != fold(t) and (ROOT / "out_note" / f"{o}.json").exists()]
        lib = "\n".join(f"{i}｜{'失败' if V.fail(o) else '做对'}｜{V.core(o)}" for i, o in enumerate(pool))
        try:
            r = V.claude(V.SEL.format(q=V.core(t), lib=lib), model, "fail")
            ids = [pool[int(x)] for x in r["fail"][:2] if V.fail(pool[int(x)])] + [pool[int(x)] for x in r["pass"][:2] if not V.fail(pool[int(x)])]
        except Exception as e:
            return t, f"err {e}"
        (out / f"{t}.json").write_text(json.dumps(ids)); return t, "ok"
    V.run(ALL, f, jobs)
else:
    arm, model = sys.argv[2], sys.argv[3]; short = model.replace("claude-", "").replace("-5-5", "")
    out = ROOT / "out_judge_full" / f"{arm}_{short}"; out.mkdir(parents=True, exist_ok=True)
    def f(t):
        if (out / f"{t}.json").exists(): return t, "skip"
        cases, ask = "", ""
        if arm == "case":
            ids = json.load(open(ROOT / "out_sel_full" / f"{t}.json"))
            cases = "===== 参照：这个智能体以前做过的题（同样格式的档案 + 真实结果）=====\n" + "".join(V.case_text(o, i + 1) for i, o in enumerate(ids))
            ask = "请先把新题和每个案例对照：新题在关键难点上更像哪几个、比它们更难还是更容易，再给出失败概率。\n"
        try:
            r = V.claude(V.JUDGE.format(agent=V.AGENT, cases=cases, issue=D[t]["issue"][:6000], dos=V.DOS(t), ask=ask), model, "p_fail")
        except Exception as e:
            return t, f"err {e}"
        r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
    V.run(ALL, f, jobs)
