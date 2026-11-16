#!/usr/bin/env python3
"""第 5 章归因「查」：对 DS 真挂且有阅卷归因的旧题，问档案（动手前写的）有没有写到真实失败点。
只用于事后分析，不进任何预测输入。输出 out_found/<t>.json：{"found":"hit|partial|miss","section":1~7或0,"quote":"档案原句","why":"..."}
用法：chk_found.py <模型> [--jobs N]"""
import sys, json, os
import v4 as V
ROOT = V.ROOT
model = sys.argv[1]; jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
out = ROOT / "out_found"; out.mkdir(exist_ok=True)
AT = V.AT; TS = sorted(t for t in AT if (ROOT / "out_dossier" / f"{t}.md").exists())
P = """下面是一道真实仓库题在「动手前」写的仓库档案，以及事后阅卷得出的编程智能体真实失败原因。
请判断：档案有没有写到导致失败的那个具体点（同一个文件/函数、同一个边界条件、同一处并列实现或约定）。
- hit：档案明确写到了这个点（哪怕没说它会导致失败）
- partial：档案提到了相关区域或方向，但没写到具体点
- miss：档案完全没涉及
只输出一行 JSON：{{"found":"hit|partial|miss","section":写到的那一节编号1~7（miss 填0）,"quote":"档案里最相关的原句（≤60字，miss 留空）","why":"一句话（≤50字）"}}

===== 动手前仓库档案 =====
{dos}
===== 事后阅卷：失败在哪 =====
{what}
===== 事后阅卷：为什么 =====
{why}
===== 事后阅卷：事前能否看出 =====
{pred}"""
def f(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    a = AT[t]
    try:
        r = V.claude(P.format(dos=V.DOS(t), what=str(a["L1_what"])[:2500], why=str(a["L2_why"])[:1500], pred=str(a["L3_predictable"])[:800]), model, "found")
    except Exception as e:
        return t, f"err {e}"
    r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
if __name__ == "__main__":
    print(len(TS), "tasks"); V.run(TS, f, jobs)
