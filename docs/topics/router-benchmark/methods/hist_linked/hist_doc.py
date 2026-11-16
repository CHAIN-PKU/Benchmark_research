#!/usr/bin/env python3
"""历史数据文案（crc 19:16：DS 做题的挂/过原因 + 判断者在哪判对判错、被什么误导，联动整理成一份文案）。
  write <模型>        : 每折用本折材料写一份文案 → out_hdoc/doc_fold<f>.md   [Sonnet]
     材料 = ① 本折挂/过成对对比的区分清单 + 本折历史挂率（anchors） ② 本折 Sonnet 判断者漏报/误报/判对的归因（out_jerr）
           ③ 本折题上 DS/GLM 当判断者的误判归因（xmodel/out_disagree）
  judge <模型>        : 档案 + 另一折文案 → out_hdoc/judge_<m>/<t>.json"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; S = V.S; D = V.D
FOLD = json.load(open(S / "refjudge/repo_fold.json")); fold = lambda t: FOLD[D[t]["repo"]]
O = ROOT / "out_hdoc"; O.mkdir(exist_ok=True)
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D and D[os.path.basename(f)[:-3]]["repo"] in FOLD)
W = """你要为「动手前判断者」写一份历史经验文案。判断者以后会读：新题的题面 + 动手前仓库档案 + 这份文案，然后估计编程智能体 DeepSeek 会不会挂。
下面是从一批旧题（真实成败已知）整理出的三类材料。请联动三类材料，写一份 ≤1500 字的中文文案，要求：
1. 先写「DS 什么时候挂、什么时候过」：只写挂题与过题之间真正有区别的信号（两边都常见的坑不要写），每条带历史挂率数字。
2. 再写「判断者常犯的误判」：漏报时被什么骗了、误报时被什么吓到了，各自正确该看什么信号；要写成可操作的判断步骤。
3. 每条结论配一个极短的真实对照（一题挂 vs 一题过，一句话各自说清），不写仓库名以外的长细节。
4. 不要写泛泛的「注意边界」之类；每条都必须能帮判断者把挂题和过题分开。
直接输出文案正文（Markdown），不要其他内容。

===== 材料一：DS 挂题 vs 最像过题的区分清单 + 本批历史挂率 =====
{anchors}
===== 材料二：Sonnet 当判断者，在本批题上的漏报 / 误报 / 判对归因 =====
{jerr}
===== 材料三：DS、GLM 当判断者时的误判归因（本批题）=====
{dis}"""
def anchors_text(f):
    A = json.load(open(ROOT / "out_con" / f"anchors_fold{f}.json")); pc = lambda x: f"{x[0]}/{x[1]}" if x[1] else "无"
    return f"本批 {A['n']} 道，整体挂率 {A['base']:.0%}\n" + "\n".join(f"{c['id']}. {c['question']}｜挂侧：{c['fail_side']}（历史挂 {pc(c['fail_hi'])}）｜过侧：{c['pass_side']}（历史挂 {pc(c['fail_lo'])}）" for c in A["items"])
def jerr_text(f):
    R = [json.load(open(p)) for p in glob.glob(str(ROOT / "out_jerr/*.json"))]
    return "\n".join(f"[{r['kind']}] {r['task']} p={r['p']}｜判断依据/被带偏：{r['misled_by']}｜真正信号：{r['true_signal']}｜经验：{r['lesson']}" for r in R if r["fold"] == f)
def dis_text(f):
    R = [json.load(open(p)) for p in glob.glob(str(S / "xmodel/out_disagree/*.json"))]
    return "\n".join(f"[{r['model']}当判断者，{r['main']}] {r['task']} 它给 {r['b_p']}、Sonnet 给 {r['a_p']}、14 家 {r['pub_fail']}/14 没做对｜{r['b_mistake']}" for r in R if r["task"] in D and D[r["task"]]["repo"] in FOLD and fold(r["task"]) == f) or "（本批无）"
WB = W.replace("请联动三类材料，写一份 ≤1500 字的中文文案，要求：", "请联动三类材料，写一份 ≤1500 字的中文文案。重要：成功经验和失败经验必须各占一半篇幅——学习不能只学失败的点，也要学它是怎么做对的。要求：\n0. 开头先写「DS 大多数题怎么做对的」：本批整体挂率只有约 25%，写清哪些情形下 DS 稳定做对、为什么，配真实例子；判断者默认应偏向「能做对」，只有出现明确的挂侧信号才上调。")
WB = WB.replace("1. 先写「DS 什么时候挂、什么时候过」：只写挂题与过题之间真正有区别的信号（两边都常见的坑不要写），每条带历史挂率数字。", "1. 再写「挂和过的区别」：每条挂的信号必须配一条对应的过的信号，同样详细，各带历史挂率数字；两边都常见的坑不要写。")
WB = WB.replace("2. 再写「判断者常犯的误判」：漏报时被什么骗了、误报时被什么吓到了", "2. 再写「判断者常犯的误判」：误报（把能做对的题判成会挂）和漏报各占一半篇幅，误报时被什么吓到了、漏报时被什么骗了")
ASK = "请先按历史经验文案里的判断步骤，逐条检查新题，再给出失败概率。\n"
if __name__ == "__main__":
    step = sys.argv[1]
    if step == "write":
        model = sys.argv[2]
        for f in sorted(set(FOLD.values())):
            p = W.format(anchors=anchors_text(f), jerr=jerr_text(f), dis=dis_text(f))
            import subprocess
            r = subprocess.run(["claude", "-p", p, "--output-format", "json", "--model", model, "--max-turns", "1", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                                "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"], cwd="/tmp", capture_output=True, text=True, timeout=600)
            txt = json.loads(r.stdout).get("result", ""); (O / f"doc_fold{f}.md").write_text(txt); print(f, len(txt), "chars")
    elif step == "writebal":
        model = sys.argv[2]
        for f in sorted(set(FOLD.values())):
            import subprocess
            r = subprocess.run(["claude", "-p", WB.format(anchors=anchors_text(f), jerr=jerr_text(f), dis=dis_text(f)), "--output-format", "json", "--model", model, "--max-turns", "1", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                                "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"], cwd="/tmp", capture_output=True, text=True, timeout=600)
            txt = json.loads(r.stdout).get("result", ""); (O / f"docbal_fold{f}.md").write_text(txt); print(f, len(txt), "chars")
    elif step == "proscons":  # 不给历史：先列有利条件、再列风险，再给概率
        model = sys.argv[2]; short = model.replace("claude-", "").replace("-5-5", "")
        out = O / f"proscons_{short}"; out.mkdir(exist_ok=True); jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
        PC = "请先列出这道题对智能体有利的条件（例如根因已定位、改动局部、有复现与明确期望、有现成先例或可对照的测试），再列出风险，权衡两边后给出失败概率。\n"
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            try: r = V.claude(V.JUDGE.format(agent=V.AGENT, cases="", issue=D[t]["issue"][:6000], dos=V.DOS(t), ask=PC), model, "p_fail"); float(r["p_fail"])
            except Exception as e: return t, f"err {e}"
            r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(ALL, f, jobs)
    elif step == "judge":
        model = sys.argv[2]; short = model.replace("claude-", "").replace("-5-5", "")
        DOC = "docbal" if "--bal" in sys.argv else "doc"
        out = O / (f"judgebal_{short}" if "--bal" in sys.argv else f"judge_{short}"); out.mkdir(exist_ok=True)
        jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            other = [x for x in set(FOLD.values()) if x != fold(t)][0]
            doc = "===== 历史经验文案（来自其他仓库的旧题）=====\n" + (O / f"{DOC}_fold{other}.md").read_text() + "\n"
            try: r = V.claude(V.JUDGE.format(agent=V.AGENT, cases=doc, issue=D[t]["issue"][:6000], dos=V.DOS(t), ask=ASK), model, "p_fail"); float(r["p_fail"])
            except Exception as e: return t, f"err {e}"
            r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        V.run(ALL, f, jobs)
