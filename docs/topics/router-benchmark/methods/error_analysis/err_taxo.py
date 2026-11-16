#!/usr/bin/env python3
"""判错归因（只用 DS 自己的旧题 + 档案+Sonnet 判断者）：
漏报 = DS 挂且判断者 p ≤ 中位数；误报 = DS 过且 p ≥ 第 75 百分位。
Sonnet 对照 DS 真实结果与真实隐藏测试，把每个错归到固定分类（可多选主因 1 个 + 次因 1 个），并写「判断者本来应该注意到什么」。只用于分析。
输出 out_err/<t>.json"""
import sys, json, os, glob
import numpy as np
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_err"; O.mkdir(exist_ok=True)
J = {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(str(ROOT / "out_judge_full/dos_sonnet/*.json"))}
ts = [t for t in J if t in D]; p = np.array([J[t]["p_fail"] for t in ts])
FN = [t for t in ts if V.fail(t) and J[t]["p_fail"] <= np.median(p)]; FP = [t for t in ts if not V.fail(t) and J[t]["p_fail"] >= np.percentile(p, 75)]
CAT_FN = {"A": "题面自带误导线索（补丁方向反、平台字样、链接指错）判断者没识别", "B": "隐藏测试断言了题面没写明的期望（二选一、异常类型、输出细节），判断者没意识到", "C": "对称/并列的另一侧（读写成对、并列实现）被漏改，判断者以为 DS 会覆盖", "D": "与现有测试/约定冲突，判断者没看出", "E": "被「改动小、根因明确」安抚，低估了实现里的陷阱", "F": "档案里根本没有该信息（查证没覆盖）", "G": "无法从题面/档案预判（运气/随机）"}
CAT_FP = {"H": "被「难查、根因未证实、需复现」吓到，但实现其实简单", "I": "被档案列出的坑数量吓到，这些坑隐藏测试并没考", "J": "高估隐藏测试的严格程度（逐字匹配、多种写法），实际测试宽松", "K": "没认出仓库里的现成先例/模板，实际照抄即可", "L": "题面已给出明确修法/期望，判断者仍给高", "M": "无法预判（DS 这次运气好）"}
P = """一个「动手前判断者」读了下面这道真实仓库题的题面和动手前仓库档案，估计编程智能体 DeepSeek 失败的概率，事后结果已知。请分析判断者为什么判错。
这道题的错误类型：{kind}（漏报=DS 实际挂了，判断者却给低概率；误报=DS 实际做对了，判断者却给高概率）。
请从下面固定分类里选 1 个主因（和可选 1 个次因），再写一句「判断者本来应该注意到什么才能判对」（必须是只看题面+档案就能做的动作，≤50字）。
{cats}
只输出一行 JSON：{{"main":"字母","second":"字母或空","should_notice":"一句话","text_evidence":"题面或档案里支持这个判断的原句（≤50字）"}}

===== 题面 =====
{issue}
===== 动手前档案 =====
{dos}
===== 判断者给出 =====
p_fail={p}；理由：{reason}
===== 事后：DS 结果 =====
{res}{at}
===== 事后：真实隐藏测试（节选）=====
{test}"""
def f(job):
    t, kind = job
    if (O / f"{t}.json").exists(): return t, "skip"
    cats = CAT_FN if kind == "漏报" else CAT_FP
    a = V.AT.get(t); at = f"\n阅卷：{str(a['L1_what'])[:700]}" if a and V.fail(t) else ""
    try: r = V.claude(P.format(kind=kind, cats="\n".join(f"{k} {v}" for k, v in cats.items()), issue=D[t]["issue"][:3500], dos=V.DOS(t)[:5000], p=J[t]["p_fail"], reason=J[t].get("reason", ""), res=f"{D[t]['passes']}/{D[t]['runs']} 次通过", at=at, test=D[t]["test"][:2500]), "claude-sonnet-5-5", "main")
    except Exception as e: return t, f"err {e}"
    r.update(task=t, kind=kind, p=J[t]["p_fail"]); (O / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
if __name__ == "__main__":
    print(len(FN), "漏报", len(FP), "误报"); V.run([(t, "漏报") for t in FN] + [(t, "误报") for t in FP], f, 4)
