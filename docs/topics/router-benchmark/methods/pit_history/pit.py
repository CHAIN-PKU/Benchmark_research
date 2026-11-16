#!/usr/bin/env python3
"""坑级历史（crc 11-16 17:52：历史重点是 DS 在哪类改动上容易挂）。
  extract <模型> : 从每道旧题档案抽 3~6 个坑并分类 → out_pit/extract/<t>.json            [Haiku]
  label   <模型> : DS 挂且有阅卷归因的题，判哪个坑是真实失败点 → out_pit/label/<t>.json  [Haiku]（做对题的坑全记「躲过」）
  table   <模型> : 每折、每类坑：踩/躲计数 + 分界规律 + 踩/躲各 1 例 → out_pit/table_fold<f>.json  [Sonnet]
  judge <hist|nohist> <模型> : 逐坑估概率并合成 p_fail；hist 给另一折的踩坑表，nohist 不给（对照）→ out_pit/judge_<arm>_<m>/<t>.json
用法：pit.py <步骤> ... [--jobs N]"""
import sys, json, os, glob, random
import v4 as V
ROOT = V.ROOT; S = V.S; D = V.D
FOLD = json.load(open(S / "refjudge/repo_fold.json"))
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D and D[os.path.basename(f)[:-3]]["repo"] in FOLD)
fold = lambda t: FOLD[D[t]["repo"]]
O = ROOT / "out_pit"; jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 6
TYPES = {"T1": "边界/隐含行为：只有隐藏测试才会考、题面没明说的边界或行为",
         "T2": "并列与牵连：并列实现、成对方法、多个调用点需要同步改",
         "T3": "约定与形状：现有约定、断言格式、错误信息、返回值/API 形状要对上",
         "T4": "题面误导：题面或修法建议与真实需求/现有测试不一致",
         "T5": "定位与规模：改动位置难找、分散、跨文件多",
         "T6": "其他"}
TT = "\n".join(f"{k} {v}" for k, v in TYPES.items())
EX = """下面是一道真实仓库任务的动手前仓库档案。请把档案里提到的、可能导致修复不过隐藏测试的「坑」逐个列出（3~6 个，按严重程度排序），每个坑归入一类：
{tt}
只输出一行 JSON：{{"pits":[{{"id":1,"type":"T1~T6","desc":"具体是什么坑（≤50字，写清在哪个函数/哪种输入）"}}]}}

===== 题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}"""
LB = """一道真实仓库任务，动手前列出了以下几个坑；事后阅卷给出了编程智能体真实失败的原因。请判断真实失败对应哪个坑（可多个；都对不上填空表）。
只输出一行 JSON：{{"fell":[坑编号],"why":"一句话（≤40字）"}}

===== 坑 =====
{pits}
===== 阅卷：失败在哪 =====
{what}
===== 阅卷：为什么 =====
{why}"""
TB = """下面是编程智能体 DeepSeek 在一类「坑」上的历史记录：每条是一道旧题里的这类坑，以及 DS 最后「踩了」（因此挂了）还是「躲过」（题做对了）。
坑的类型：{tname}
请总结：DS 在这类坑上，什么情况下会踩、什么情况下能躲过（分界规律），要具体、可用于判断新题。
只输出一行 JSON：{{"rule":"分界规律（≤150字）","fell_eg":"挑 1 条踩了的原文","avoid_eg":"挑 1 条躲过的、和踩的最像的原文"}}

===== 踩了（{nf} 条）=====
{fell}
===== 躲过（{na} 条，随机抽样最多 40 条）=====
{avoid}"""
JG = """判断{agent}修好下面这道题、并通过维护者隐藏测试的可能性。不要使用对上游修法的记忆。
做法：对下面列出的每个坑，单独估计「这个坑会被隐藏测试考到、而且这个智能体会踩」的概率；再给整题失败概率（一般不低于最大的单坑概率）。
{table}
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
===== 档案里的坑 =====
{pits}

只输出一行 JSON：{{"per_pit":[{{"id":1,"p":0~1}}],"p_fail":0~1,"reason":"一句话（≤60字）"}}"""
def pits_text(t): return "\n".join(f"{p['id']}. [{p['type']}] {p['desc']}" for p in json.load(open(O / "extract" / f"{t}.json"))["pits"])
def records(f):
    """训练折的坑级记录：(类型, 描述, 踩/躲)。挂但无归因或对不上的题跳过。"""
    R = []
    for t in ALL:
        if fold(t) != f or not (O / "extract" / f"{t}.json").exists(): continue
        P = json.load(open(O / "extract" / f"{t}.json"))["pits"]
        if V.fail(t):
            lf = O / "label" / f"{t}.json"
            if not lf.exists(): continue
            fell = set(json.load(open(lf)).get("fell", []))
            if not fell: continue
            R += [(p["type"], p["desc"], p["id"] in fell) for p in P]
        else:
            R += [(p["type"], p["desc"], False) for p in P]
    return R
def table_text(f):
    T = json.load(open(O / f"table_fold{f}.json"))
    s = "===== 参照：这个智能体（DS）在各类坑上的历史踩坑表（来自其他仓库的旧题）=====\n"
    for k, v in T.items():
        s += f"{k} {TYPES[k]}：历史上踩 {v['nf']} 次 / 躲过 {v['na']} 次。规律：{v.get('rule','')}\n   踩的例子：{v.get('fell_eg','')}\n   躲过的例子：{v.get('avoid_eg','')}\n"
    return s
if __name__ == "__main__":
    step = sys.argv[1]
    if step == "extract":
        model = sys.argv[2]; out = O / "extract"; out.mkdir(parents=True, exist_ok=True)
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            try: r = V.claude(EX.format(tt=TT, issue=D[t]["issue"][:6000], dos=V.DOS(t)), model, "pits"); assert r["pits"]
            except Exception as e: return t, f"err {e}"
            (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(ALL[:2] if "--smoke" in sys.argv else ALL, f, jobs)
    elif step == "label":
        model = sys.argv[2]; out = O / "label"; out.mkdir(parents=True, exist_ok=True)
        ts = [t for t in ALL if V.fail(t) and t in V.AT]
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            a = V.AT[t]
            try: r = V.claude(LB.format(pits=pits_text(t), what=str(a["L1_what"])[:2500], why=str(a["L2_why"])[:1500]), model, "fell")
            except Exception as e: return t, f"err {e}"
            (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(ts, f, jobs)
    elif step == "table":
        model = sys.argv[2]
        for fo in sorted(set(FOLD.values())):
            R = records(fo); T = {}
            for k in TYPES:
                fell = [d for ty, d, x in R if ty == k and x]; av = [d for ty, d, x in R if ty == k and not x]
                T[k] = {"nf": len(fell), "na": len(av)}
                if fell and av:
                    random.seed(0); avs = random.sample(av, min(40, len(av)))
                    T[k].update(V.claude(TB.format(tname=TYPES[k], nf=len(fell), na=len(av), fell="\n".join("- " + d for d in fell), avoid="\n".join("- " + d for d in avs)), model, "rule"))
                print(fo, k, T[k]["nf"], T[k]["na"], flush=True)
            (O / f"table_fold{fo}.json").write_text(json.dumps(T, ensure_ascii=False, indent=1))
    elif step == "dostable":  # 整体判断（与档案+Haiku 同一提示）+ 另一折踩坑表；不给逐坑格式
        model = sys.argv[2]; short = model.replace("claude-", "").replace("-5-5", "")
        out = O / f"judge_dostable_{short}"; out.mkdir(parents=True, exist_ok=True)
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            other = [x for x in set(FOLD.values()) if x != fold(t)][0]
            try: r = V.claude(V.JUDGE.format(agent=V.AGENT, cases=table_text(other), issue=D[t]["issue"][:6000], dos=V.DOS(t), ask="请对照踩坑表：新题档案里的坑，更像这个智能体历史上会踩的那种，还是会躲过的那种。\n"), model, "p_fail"); float(r["p_fail"])
            except Exception as e: return t, f"err {e}"
            r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(ALL, f, jobs)
    elif step == "judge":
        arm, model = sys.argv[2], sys.argv[3]; short = model.replace("claude-", "").replace("-5-5", "")
        out = O / f"judge_{arm}_{short}"; out.mkdir(parents=True, exist_ok=True)
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            other = [x for x in set(FOLD.values()) if x != fold(t)][0]
            table = table_text(other) if arm == "hist" else ""
            try: r = V.claude(JG.format(agent=V.AGENT, table=table, issue=D[t]["issue"][:6000], dos=V.DOS(t), pits=pits_text(t)), model, "p_fail"); float(r["p_fail"])
            except Exception as e: return t, f"err {e}"
            r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(ALL, f, jobs)
