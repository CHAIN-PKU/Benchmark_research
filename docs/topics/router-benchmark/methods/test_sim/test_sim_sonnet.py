#!/usr/bin/env python3
"""第一性原理：失败的本质是「隐藏测试要求的行为，题面+仓库没有唯一确定」（欠规范）。让判断者模拟维护者写测试：
  gen   ：对每题采样 K=3 次「维护者会加的测试要点（≤6 条，具体到输入/期望）」  → out_ts/gen/<t>_<k>.json   [Haiku]
  cmp   ：与真实隐藏测试对照，打「覆盖度」0~1（只用于验证，推理时不可用）       → out_ts/cmp/<t>.json
  cons  ：3 份要点之间的一致度 0~1（推理时可用：分歧=欠规范）                    → out_ts/cons/<t>.json
输入只有题面 + 动手前档案。真实隐藏测试仅在 cmp 里出现，绝不进 gen/cons。"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_ts_sonnet"
for s in ("gen", "cmp", "cons"): (O / s).mkdir(parents=True, exist_ok=True)
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D and D[os.path.basename(f)[:-3]].get("test"))
G = """下面是一道开源仓库的修复题（题面）和动手前仓库档案。请想象你是这个仓库的维护者，为这个修复添加测试。写出你会加的测试要点，每条具体到「输入/场景 → 期望行为」，最多 6 条，按你认为最可能出现的顺序。不要使用对上游真实测试的记忆。
只输出一行 JSON：{{"points":["要点1","要点2",...]}}

===== 题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}"""
CM = """下面是维护者真实的隐藏测试（diff）和一份「预测的测试要点」。请数一下：真实测试里的断言/场景，有多大比例被预测要点覆盖（同一输入/场景、同一期望行为才算覆盖）。
只输出一行 JSON：{{"covered":0~1,"n_real":真实断言/场景个数,"why":"一句话（≤50字）"}}

===== 真实隐藏测试 =====
{test}
===== 预测要点 =====
{pts}"""
CS = """下面是三份独立写出的「维护者会加的测试要点」。请评估它们之间的一致度：三份在「期望行为」上是否说的是同一件事（同一输入给出同一期望才算一致；只是措辞或覆盖面不同不算分歧；期望本身互相矛盾、或一份有另两份没有的关键期望，算分歧）。
只输出一行 JSON：{{"agree":0~1,"conflict":"最主要的分歧点（≤50字，没有留空）"}}

--- 第 1 份 ---
{a}
--- 第 2 份 ---
{b}
--- 第 3 份 ---
{c}"""
def f(t):
    pts = []
    for k in range(3):
        fn = O / "gen" / f"{t}_{k}.json"
        if fn.exists(): pts.append(json.load(open(fn))["points"]); continue
        try: r = V.claude(G.format(issue=D[t]["issue"][:6000], dos=V.DOS(t)), "claude-sonnet-5-5", "points"); assert r["points"]
        except Exception as e: return t, f"err gen {e}"
        fn.write_text(json.dumps(r, ensure_ascii=False)); pts.append(r["points"])
    fmt = lambda p: "\n".join(f"- {x}" for x in p)
    if not (O / "cmp" / f"{t}.json").exists():
        try:
            rs = [V.claude(CM.format(test=D[t]["test"][:7000], pts=fmt(p)), "claude-haiku-5-5", "covered") for p in pts]
            (O / "cmp" / f"{t}.json").write_text(json.dumps({"covered": [float(r["covered"]) for r in rs], "n_real": rs[0].get("n_real")}))
        except Exception as e: return t, f"err cmp {e}"
    return t, "ok"
import random
random.seed(20261117); fl = [t for t in ALL if V.fail(t)]; ps = [t for t in ALL if not V.fail(t)]
SUB = sorted(random.sample(fl, 30) + random.sample(ps, 30)); json.dump(SUB, open(O / "subset.json", "w"))
V.run(SUB, f, 6)
