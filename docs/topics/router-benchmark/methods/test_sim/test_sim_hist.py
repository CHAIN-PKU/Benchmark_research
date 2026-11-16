#!/usr/bin/env python3
"""出题人历年真题：给模拟器看同仓库「其他」任务的真实隐藏测试（留一，不含本题），再写本题的测试要点；
与真实测试对照覆盖度，和不看历年真题的版本（out_ts）比。
输入：本题题面+档案 + 同仓库其他任务的隐藏测试 diff（≤3 个，各截 2500 字）。真实本题测试只在 cmp 里出现。
用法：test_sim_hist.py run → out_ts_hist/{gen,cmp}"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_ts_hist"
for s in ("gen", "cmp"): (O / s).mkdir(parents=True, exist_ok=True)
import importlib.util
src = open(ROOT / "test_sim.py").read()
CM = src.split('CM = """')[1].split('"""')[0]
G = """下面是一道开源仓库的修复题（题面）和动手前仓库档案；另外附上这个仓库的维护者以前为其他修复添加的测试（他们的出题习惯）。请想象你是这个仓库的维护者，为本题的修复添加测试。写出你会加的测试要点，每条具体到「输入/场景 → 期望行为」，最多 6 条，按你认为最可能出现的顺序。参考他们以前的写法（断言风格、爱测的边界、测试位置），但不要照搬无关内容；不要使用对本题上游真实测试的记忆。
只输出一行 JSON：{{"points":["要点1","要点2",...]}}

===== 该维护者以前的测试（其他修复）=====
{past}
===== 本题题面 =====
{issue}
===== 本题动手前仓库档案 =====
{dos}"""
by = {}
for t in D:
    if D[t].get("test") and (ROOT / "out_dossier" / f"{t}.md").exists(): by.setdefault(D[t]["repo"], []).append(t)
ALL = sorted(t for t in D if D[t].get("test") and (ROOT / "out_dossier" / f"{t}.md").exists() and len(by[D[t]["repo"]]) >= 2)
def past(t):
    o = [u for u in by[D[t]["repo"]] if u != t][:3]
    return "\n\n".join(f"### 以前的修复 {u}\n{D[u]['test'][:2500]}" for u in o)
def f(t):
    pts = []
    for k in range(3):
        fn = O / "gen" / f"{t}_{k}.json"
        if fn.exists(): pts.append(json.load(open(fn))["points"]); continue
        try: r = V.claude(G.format(past=past(t), issue=D[t]["issue"][:5000], dos=V.DOS(t)), "claude-haiku-5-5", "points"); assert r["points"]
        except Exception as e: return t, f"err gen {e}"
        fn.write_text(json.dumps(r, ensure_ascii=False)); pts.append(r["points"])
    if not (O / "cmp" / f"{t}.json").exists():
        fmt = lambda p: "\n".join(f"- {x}" for x in p)
        try: rs = [V.claude(CM.format(test=D[t]["test"][:7000], pts=fmt(p)), "claude-haiku-5-5", "covered") for p in pts]; (O / "cmp" / f"{t}.json").write_text(json.dumps({"covered": [float(r["covered"]) for r in rs]}))
        except Exception as e: return t, f"err cmp {e}"
    return t, "ok"
print(len(ALL), "道有同仓库其他任务")
V.run(ALL, f, 6)
