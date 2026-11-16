#!/usr/bin/env python3
"""方法 v4（小样 30 道）：
  note   : 为案例池每道题写事后注记（标准修复改了哪里、DS 结果与原因、教训）→ out_note/<t>.json   [Sonnet]
  select : 为每道目标题从案例池挑 2 挂 2 过最相似的案例（看两边档案的「难点一句话」与结构）→ out_sel/<t>.json [Haiku]
  judge  : 判断。组别 dos（只给档案）/ case（档案 + 4 个完整案例）→ out_judge/<arm>_<model>/<t>.json
用法：v4.py note <模型> | v4.py select <模型> | v4.py judge <dos|case> <模型>   [--jobs N]"""
import sys, json, pathlib, re, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
step = sys.argv[1]
D = json.load(open(S / "tagging/tag_data.json"))
AT = {json.loads(l)["task"]: json.loads(l) for l in open("/Users/aibasis/Benchmark_Research/Benchmark_research/docs/topics/router-benchmark/attribution_v2/deep_attribution_46.jsonl")}
TG = json.load(open(ROOT / "targets30.json")); PL = json.load(open(ROOT / "pool30.json"))
DOS = lambda t: (ROOT / "out_dossier" / f"{t}.md").read_text()
fail = lambda t: D[t]["passes"] < D[t]["runs"]
def core(t):
    m = re.search(r"(?:【7[^】]*】|#+\s*7[^\n]*\n)(.*)", DOS(t), re.S); return (m.group(1) if m else DOS(t)[-300:]).strip()[:200]
def claude(prompt, model, need):
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=400)
    txt = json.loads(p.stdout).get("result", ""); dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(txt) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(txt, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and need in obj: return obj
    raise ValueError("no json: " + txt[-200:])
NOTE = """下面是一道真实仓库任务的「动手前仓库档案」、标准修复，以及编程智能体 DeepSeek 的真实结果。请写一段事后注记，帮助以后判断类似的题。
只输出一行 JSON：{{"gold_changed":"标准修复实际改了哪些地方（≤80字）","ds_outcome":"DS 做对或做错了什么、错在哪（≤80字）","lesson":"从动手前档案里，本来能看出什么信号预示这个结果（≤80字）"}}

【动手前档案】
{dos}
【标准修复】
{gold}
【DS 结果】{res}{attr}"""
SEL = """下面是一道新题的难点，以及一个案例库（每个案例一行：编号、结果、难点）。请挑出和新题「难在同一类地方」最像的 2 个失败案例和 2 个做对案例。
只输出一行 JSON：{{"fail":["编号","编号"],"pass":["编号","编号"]}}

【新题难点】{q}
【案例库】
{lib}"""
AGENT = "编程智能体 DeepSeek（整体约 75%~80% 能做对；习惯照题面实现，通常只为题面给的例子写自测）"
JUDGE = """判断{agent}修好下面这道新题、并通过维护者隐藏测试的可能性。不要使用对上游修法的记忆。
{cases}
===== 新题：完整题面 =====
{issue}
===== 新题：动手前仓库档案 =====
{dos}

{ask}只输出一行 JSON：{{"p_fail":0~1,"reason":"一句话（≤60字）"}}"""
def case_text(o, i):
    n = json.load(open(ROOT / "out_note" / f"{o}.json"))
    return (f"----- 案例{i}（{'失败' if fail(o) else '做对'}，{D[o]['passes']}/{D[o]['runs']} 次通过）-----\n"
            f"【当时的动手前档案】\n{DOS(o)[:2500]}\n【标准修复改了】{n['gold_changed']}\n【DS 结果】{n['ds_outcome']}\n【教训】{n['lesson']}\n")
def run(items, fn, jobs):
    with cf.ThreadPoolExecutor(jobs) as ex:
        for k, s in ex.map(fn, items): print(k, s, flush=True)
if __name__ == "__main__":
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
    if step == "note":
        model = sys.argv[2]; out = ROOT / "out_note"; out.mkdir(exist_ok=True)
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            a = AT.get(t); attr = f"\n【阅卷归因】{a['L1_what']}；{a['L2_why']}" if a and fail(t) else ""
            try:
                r = claude(NOTE.format(dos=DOS(t)[:3000], gold=D[t].get("gold", "")[:3000], res=f"{D[t]['passes']}/{D[t]['runs']} 次通过", attr=attr), model, "lesson")
            except Exception as e:
                return t, f"err {e}"
            (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        run(PL, f, jobs)
    elif step == "select":
        model = sys.argv[2]; out = ROOT / "out_sel"; out.mkdir(exist_ok=True)
        lib = "\n".join(f"{i}｜{'失败' if fail(o) else '做对'}｜{core(o)}" for i, o in enumerate(PL))
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            try:
                r = claude(SEL.format(q=core(t), lib=lib), model, "fail")
                ids = [PL[int(x)] for x in r["fail"][:2] if fail(PL[int(x)])] + [PL[int(x)] for x in r["pass"][:2] if not fail(PL[int(x)])]
            except Exception as e:
                return t, f"err {e}"
            (out / f"{t}.json").write_text(json.dumps(ids)); return t, "ok"
        run(TG, f, jobs)
    else:
        arm, model = sys.argv[2], sys.argv[3]; short = model.replace("claude-", "").replace("-5-5", "")
        out = ROOT / "out_judge" / f"{arm}_{short}"; out.mkdir(parents=True, exist_ok=True)
        def f(t):
            if (out / f"{t}.json").exists(): return t, "skip"
            cases, ask = "", ""
            if arm == "case":
                ids = json.load(open(ROOT / "out_sel" / f"{t}.json"))
                cases = "===== 参照：这个智能体以前做过的题（同样格式的档案 + 真实结果）=====\n" + "".join(case_text(o, i + 1) for i, o in enumerate(ids))
                ask = "请先把新题和每个案例对照：新题在关键难点上更像哪几个、比它们更难还是更容易，再给出失败概率。\n"
            try:
                r = claude(JUDGE.format(agent=AGENT, cases=cases, issue=D[t]["issue"][:6000], dos=DOS(t), ask=ask), model, "p_fail")
            except Exception as e:
                return t, f"err {e}"
            r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
        run(TG, f, jobs)
