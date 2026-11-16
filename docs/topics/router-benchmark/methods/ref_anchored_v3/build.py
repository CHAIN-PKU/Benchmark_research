#!/usr/bin/env python3
"""参照式判断 v3 —— 两步准备：
  card  : 为旧题写案例卡（事后，可看标准修复/测试/DS 结果/阅卷归因）→ out_card/<t>.json
  query : 为每道题写「事前难点」（只看题面+动手前线索）→ out_query/<t>.json
用法：build.py <card|query> <模型> [--jobs N]"""
import sys, json, pathlib, glob, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
step, model = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 6
out = ROOT / f"out_{step}"; out.mkdir(exist_ok=True)
D = json.load(open(S / "tagging/tag_data.json"))
EV = {json.load(open(f))["task"]: json.load(open(f)).get("evidence") for f in glob.glob(str(S / "train_tags/out/sonnet_tags/*.json"))}
AT = {json.loads(l)["task"]: json.loads(l) for l in open("/Users/aibasis/Benchmark_Research/Benchmark_research/docs/topics/router-benchmark/attribution_v2/deep_attribution_46.jsonl")}
TS = sorted(t for t in D if t in EV)
def ev(t):
    e = EV.get(t) or []
    return "\n".join(f"- {x}" for x in (e if isinstance(e, list) else [e]))
CARD = """你在为「编程智能体 DeepSeek 的历史案例库」写一张案例卡。下面是一道真实仓库任务的全部材料和 DS 的真实结果。
要求：
- core：一句话说清这道题「难在哪」（或「其实不难在哪」），抽象到不依赖项目名和具体函数名，让别的项目的题也能拿来比，≤50字。
- cues：动手前（只看题面和仓库）能看到的、和难点有关的线索，≤2 条，每条≤40字。
- verdict_reason：DS {result}的原因，一句话，≤60字。挂的写挂在哪；过的写为什么这题没难住它。
只输出一行 JSON：{{"core":"...","cues":["..."],"verdict_reason":"..."}}

【题面】
{issue}
【动手前线索】
{ev}
【标准修复（只用于你理解）】
{gold}
【DS 结果】{outcome}{attr}"""
QUERY = """下面是一道真实仓库任务的题面和动手前在仓库里查到的线索（没有答案）。
用一句话说清这道题「难在哪」，抽象到不依赖项目名和具体函数名，≤50字。
只输出一行 JSON：{{"core":"..."}}

【题面】
{issue}
【动手前线索】
{ev}"""
def one(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    v = D[t]; ok = v["passes"] == v["runs"]
    if step == "card":
        a = AT.get(t); attr = f"\n【阅卷归因】{a['L1_what']}；{a['L2_why']}" if a and not ok else ""
        prompt = CARD.format(result="做对" if ok else "失败", issue=v["issue"][:3500], ev=ev(t), gold=v.get("gold", "")[:3000],
                             outcome=f"{v['passes']}/{v['runs']} 次通过", attr=attr)
        need = "verdict_reason"
    else:
        prompt = QUERY.format(issue=v["issue"][:3500], ev=ev(t)); need = "core"
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        txt = json.loads(p.stdout).get("result", ""); dec = json.JSONDecoder()
        for i in reversed([k for k, c in enumerate(txt) if c == "{"]):
            try:
                obj, _ = dec.raw_decode(txt, i)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and need in obj:
                obj["task"] = t; (out / f"{t}.json").write_text(json.dumps(obj, ensure_ascii=False) + "\n"); return t, "ok"
        raise ValueError("no json")
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-800:]); return t, "err"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, TS): print(t, s, flush=True)
