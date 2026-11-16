#!/usr/bin/env python3
"""由判错原因直接生成「判断规则」（方法论：错误→原因→针对性指令），并做交叉检验：
折 f 的判断规则只由「另一折」的判错分析写成，再用来判折 f 的题；对比同一判断者不用规则的结果。
用法：err_instr.py write | judge <模型>"""
import sys, json, os, glob, collections
import numpy as np
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_err_instr"; O.mkdir(exist_ok=True)
FO = json.load(open(V.S / "refjudge/repo_fold.json")); fold = lambda t: FO[D[t]["repo"]]
R = [json.load(open(f)) for f in glob.glob(str(ROOT / "out_err/*.json"))]
W = """下面是一位「动手前判断者」（读题面+动手前仓库档案，估计编程智能体 DeepSeek 失败概率）在一批旧题上判错的分析：漏报（DS 实际挂了却判低）和误报（DS 实际做对了却判高），每条有原因分类和「本来应该注意到什么」。
请把它写成给判断者的「判断规则」：≤8 条，每条是一个具体动作（看档案哪里、问什么问题、什么情况下抬高、什么情况下压低），要能同时减少漏报和误报。不要写数字，不要提具体仓库或题号，不要自相矛盾；误报多的原因要写成「不要因为……而抬高」，漏报的原因要写成「看到……才抬高」。
只输出规则正文（编号列表），不要其他内容。

===== 误判分类统计 =====
{stats}
===== 逐条分析 =====
{cases}"""
if sys.argv[1] == "write":
    for f in sorted(set(FO.values())):
        L = [r for r in R if fold(r["task"]) != f]
        c = collections.Counter((r["kind"], r["main"]) for r in L); stats = "\n".join(f"{k[0]} 原因{k[1]}：{n} 个" for k, n in c.most_common())
        cases = "\n".join(f"[{r['kind']}/{r['main']}] {r['should_notice']}" for r in L)
        import subprocess
        r = subprocess.run(["claude", "-p", W.format(stats=stats, cases=cases), "--output-format", "json", "--model", "claude-sonnet-5-5", "--max-turns", "1", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands", "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"], cwd="/tmp", capture_output=True, text=True, timeout=600)
        txt = json.loads(r.stdout).get("result", ""); (O / f"rules_fold{f}.md").write_text(txt); print(f, len(txt)); print(txt)
else:
    model = sys.argv[2]; short = model.replace("claude-", "").replace("-5-5", ""); out = O / f"judge_{short}"; out.mkdir(exist_ok=True)
    ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D and D[os.path.basename(f)[:-3]]["repo"] in FO)
    def f(t):
        if (out / f"{t}.json").exists(): return t, "skip"
        rules = "===== 判断规则（由其他仓库的判错分析总结）=====\n" + (O / f"rules_fold{fold(t)}.md").read_text() + "\n"
        try: r = V.claude(V.JUDGE.format(agent=V.AGENT, cases=rules, issue=D[t]["issue"][:6000], dos=V.DOS(t), ask="请逐条对照上面的判断规则检查这道题，再给出失败概率。\n"), model, "p_fail"); float(r["p_fail"])
        except Exception as e: return t, f"err {e}"
        r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
    V.run(ALL, f, 4)
