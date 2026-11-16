#!/usr/bin/env python3
"""分解 P(挂) = Σ_坑 P(隐藏测试考到该坑) × P(执行者没处理好 | 被考到)。
本脚本做第一因子的训练标签（与执行者无关）：对每道旧题，读隐藏测试 diff，判断档案里每个坑「是否被隐藏测试实际考到」，
并记录「隐藏测试考了但档案没列的点」。标签只用于训练，绝不出现在预测输入里。
用法：hit_label.py run → out_hit/<t>.json"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_hit"; O.mkdir(exist_ok=True)
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(str(ROOT / "out_pit/extract/*.json"))}
ALL = sorted(t for t in EXT if t in D and D[t].get("test"))
P = """下面是一道修复题动手前列出的几个「坑」，以及维护者实际的隐藏测试（diff）。请判断每个坑是否被隐藏测试实际考到（测试里有断言直接依赖该点的行为：1=考到，0=没考到），并写出隐藏测试考了、但坑列表里没有的点（没有则空）。
只输出一行 JSON：{{"hit":{{"坑编号":0或1,...}},"extra":"隐藏测试考了但没列的点（≤60字，没有留空）"}}

===== 坑 =====
{pits}
===== 隐藏测试 diff =====
{test}"""
def f(t):
    if (O / f"{t}.json").exists(): return t, "skip"
    pits = "\n".join(f"{p['id']}. [{p['type']}] {p['desc']}" for p in EXT[t])
    try: r = V.claude(P.format(pits=pits, test=D[t]["test"][:7000]), "claude-haiku-5-5", "hit"); r["hit"] = {str(k): int(v) for k, v in r["hit"].items()}
    except Exception as e: return t, f"err {e}"
    r["task"] = t; (O / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
V.run(ALL, f, 6)
