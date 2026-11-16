#!/usr/bin/env python3
"""判断者误判归因（crc 19:16：强模型没判好的地方也要归因；判对/判错对照，看在哪里被误导）。
对象：档案 + Sonnet 判断（out_judge_full/dos_sonnet）。每折挑：漏报 8（DS 挂、p 最低）、误报 8（DS 过、p 最高）、
判对参照 4+4（挂且 p 最高、过且 p 最低）。Sonnet 逐题归因 → out_jerr/<t>.json"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; S = V.S; D = V.D
FOLD = json.load(open(S / "refjudge/repo_fold.json")); fold = lambda t: FOLD[D[t]["repo"]]
J = {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(str(ROOT / "out_judge_full/dos_sonnet/*.json"))}
J = {t: r for t, r in J.items() if t in D and D[t]["repo"] in FOLD}
out = ROOT / "out_jerr"; out.mkdir(exist_ok=True)
SEL = []
for fo in sorted(set(FOLD.values())):
    ts = [t for t in J if fold(t) == fo]; fl = sorted([t for t in ts if V.fail(t)], key=lambda t: J[t]["p_fail"]); ps = sorted([t for t in ts if not V.fail(t)], key=lambda t: -J[t]["p_fail"])
    SEL += [(t, "漏报") for t in fl[:8]] + [(t, "误报") for t in ps[:8]] + [(t, "判对·挂") for t in fl[-4:]] + [(t, "判对·过") for t in ps[-4:]]
P = """一个「动手前判断者」读了下面这道真实仓库题的题面和动手前仓库档案，判断编程智能体 DeepSeek 会不会挂。事后结果已知。
这道题属于：{kind}（漏报=实际挂了但判断者给低概率；误报=实际做对了但给高概率；判对=判断正确，作对照）。
请分析判断者的判断依据：它被什么带偏了（或为什么判对了），档案里哪个信号才是真正决定成败的。
只输出一行 JSON：{{"misled_by":"判断者依据/被带偏的信号（≤50字；判对时写它抓住的信号）","true_signal":"档案里真正决定成败的信号（≤50字）","section":"该信号在档案哪一节","lesson":"给以后判断者的一句经验，要能区分同类题（≤60字）"}}

===== 题面 =====
{issue}
===== 动手前档案 =====
{dos}
===== 判断者给出 =====
p_fail={p}；理由：{reason}
===== 事后结果 =====
DeepSeek {res}{at}"""
def f(job):
    t, kind = job
    if (out / f"{t}.json").exists(): return t, "skip"
    a = V.AT.get(t); at = f"\n阅卷：{str(a['L1_what'])[:800]}\n{str(a['L2_why'])[:500]}" if a and V.fail(t) else ""
    try: r = V.claude(P.format(kind=kind, issue=D[t]["issue"][:4000], dos=V.DOS(t), p=J[t]["p_fail"], reason=J[t].get("reason", ""), res=f"{D[t]['passes']}/{D[t]['runs']} 次通过", at=at), "claude-sonnet-5-5", "lesson")
    except Exception as e: return t, f"err {e}"
    r.update(task=t, kind=kind, fold=fold(t), p=J[t]["p_fail"]); (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
if __name__ == "__main__":
    print(len(SEL), "tasks"); V.run(SEL, f, 4)
