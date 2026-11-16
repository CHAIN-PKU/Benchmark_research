#!/usr/bin/env python3
"""欠规范直接度量：让判断者列出「写这些测试时，题面和仓库里找不到依据、只能靠猜的期望」，数条数并标严重度。
输入：题面 + 档案 + 三份模拟测试要点的并集。不含真实测试。输出 out_ts/assume/<t>.json"""
import json, os, glob
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_ts"; (O / "assume").mkdir(exist_ok=True)
ALL = sorted(t for t in D if all((O / "gen" / f"{t}_{k}.json").exists() for k in range(3)) and (ROOT / "out_dossier" / f"{t}.md").exists())
P = """下面是一道开源仓库修复题（题面）、动手前仓库档案，以及三份独立写出的「维护者会加的测试要点」。
请找出这些测试要点里，**题面和仓库里找不到依据、只能靠猜的期望**（例如：该报错还是返回默认值、错误信息/类型是什么、边界值怎么处理、另一侧是否也要改、输出格式的细节）。对每一条标严重度：1=猜错了也只影响边角，2=猜错了很可能让隐藏测试失败。不要列题面或档案已明确说明的。
只输出一行 JSON：{{"assumed":[{{"what":"（≤40字）","sev":1或2}}]}}

===== 题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
===== 三份测试要点 =====
{pts}"""
def f(t):
    if (O / "assume" / f"{t}.json").exists(): return t, "skip"
    pts = "\n".join(f"--- 第{k+1}份 ---\n" + "\n".join(f"- {x}" for x in json.load(open(O / 'gen' / f'{t}_{k}.json'))["points"]) for k in range(3))
    try: r = V.claude(P.format(issue=D[t]["issue"][:6000], dos=V.DOS(t), pts=pts), "claude-haiku-5-5", "assumed"); assert isinstance(r["assumed"], list)
    except Exception as e: return t, f"err {e}"
    (O / "assume" / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
V.run(ALL, f, 6)
