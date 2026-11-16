#!/usr/bin/env python3
"""固定技能/陷阱表（Q 矩阵的列）：只从所有题档案里的「坑」文本归纳，完全不看成败标签。
  build   : Sonnet 读全部坑描述，归纳 ~12 项技能/陷阱 → out_tax/taxonomy.json
  tag <模型> : 每道题让 Haiku 对每一项打 0~1（这道题在该项上的要求/暴露程度）→ out_tax/q/<t>.json
用法：taxonomy.py <build|tag> [模型] [--jobs N]"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_tax"; (O / "q_rb").mkdir(parents=True, exist_ok=True); S = V.S; ISS = {p.stem: p.read_text() for p in (S / "rebench/issue").glob("*.md")}
step = sys.argv[1]; jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 6
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(str(ROOT / "out_pit/extract/*.json"))}
TB = """下面是 {n} 条「动手前仓库档案里列出的坑」（每条是一道真实仓库修复题里，可能导致修复过不了隐藏测试的点）。
请归纳出一张固定的「技能/陷阱表」，用来给任何新题标注：共 10~14 项，互相尽量不重叠，合起来覆盖大多数坑。
每项要能让人只看「题面 + 动手前档案」就判断这道题在该项上要求高不高。不要用「改动是否简单」这类笼统项，要写成具体的技能或陷阱。
只输出一行 JSON：{{"skills":[{{"id":"S1","name":"短名（≤10字）","question":"判断这题在该项上要求多高的问题（≤45字）","high":"要求高的样子（≤50字）","low":"几乎不涉及的样子（≤40字）","count":覆盖的大致坑数}}]}}

{pits}"""
TG = """下面是一张固定的「技能/陷阱表」。请判断这道新题在每一项上的要求/暴露程度（0=几乎不涉及，1=要求很高、是主要难点，0.5=一般）。只依据题面与动手前档案，不要使用对上游修法的记忆。
{tax}
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
只输出一行 JSON：{{"q":{{"S1":0~1,...}}}}"""
def taxtext(T): return "\n".join(f"{s['id']} {s['name']}：{s['question']}｜高：{s['high']}｜低：{s['low']}" for s in T["skills"])
if step == "build":
    L = [p["desc"][:110] for t in sorted(EXT) for p in EXT[t]]
    r = V.claude(TB.format(n=len(L), pits="\n".join(f"- {x}" for x in L)), "claude-sonnet-5-5", "skills"); (O / "taxonomy.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    print(taxtext(r))
else:
    model = sys.argv[2]; T = json.load(open(O / "taxonomy.json")); ids = [s["id"] for s in T["skills"]]
    RB = sorted(p.stem for p in (ROOT / "out_dossier_rb").glob("*.md"))
    def f(t):
        if (O / "q_rb" / f"{t}.json").exists(): return t, "skip"
        try: r = V.claude(TG.format(tax=taxtext(T), issue=ISS[t][:6000], dos=(ROOT / "out_dossier_rb" / f"{t}.md").read_text()), model, "q"); assert all(i in r["q"] for i in ids)
        except Exception as e: return t, f"err {e}"
        (O / "q_rb" / f"{t}.json").write_text(json.dumps(r["q"])); return t, "ok"
    V.run(RB, f, jobs)
