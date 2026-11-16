#!/usr/bin/env python3
"""把「模拟测试」和「坑列表」接起来：对每个坑，3 份模拟测试要点里有几份覆盖了它（0~3）→ h_i = 票数/3（预测「该坑被隐藏测试考到」的概率）。
输入只有坑列表和模拟测试要点（都不含真实测试）。输出 out_ts/vote/<t>.json：{坑编号: 票数}。"""
import json, os, glob
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_ts"; (O / "vote").mkdir(exist_ok=True)
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(str(ROOT / "out_pit/extract/*.json"))}
ALL = sorted(t for t in EXT if t in D and all((O / "gen" / f"{t}_{k}.json").exists() for k in range(3)))
P = """下面是一道修复题动手前列出的几个「坑」，以及三份独立写出的「维护者会加的测试要点」。请对每个坑判断：每一份测试要点是否包含直接依赖该坑行为的断言/场景（1=包含，0=不包含）。
只输出一行 JSON：{{"votes":{{"坑编号":[第1份0或1,第2份0或1,第3份0或1],...}}}}

===== 坑 =====
{pits}
===== 三份测试要点 =====
{pts}"""
def f(t):
    if (O / "vote" / f"{t}.json").exists(): return t, "skip"
    pits = "\n".join(f"{p['id']}. {p['desc']}" for p in EXT[t])
    pts = "\n".join(f"--- 第{k+1}份 ---\n" + "\n".join(f"- {x}" for x in json.load(open(O / 'gen' / f'{t}_{k}.json'))["points"]) for k in range(3))
    try: r = V.claude(P.format(pits=pits, pts=pts), "claude-haiku-5-5", "votes"); v = {str(k): int(sum(map(int, x))) for k, x in r["votes"].items()}
    except Exception as e: return t, f"err {e}"
    (O / "vote" / f"{t}.json").write_text(json.dumps(v)); return t, "ok"
V.run(ALL, f, 6)
