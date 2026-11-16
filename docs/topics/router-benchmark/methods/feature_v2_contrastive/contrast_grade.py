#!/usr/bin/env python3
"""对照阅卷：每道 DS 挂题配同仓库 2 道 DS 做对的题，找出「事前可见、能把挂和过分开」的特征。
只用旧题（tag_data.json，192 道）。用法：contrast_grade.py <模型> [--jobs N]"""
import sys, json, pathlib, random, subprocess, glob, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
model = sys.argv[1]; jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
out = ROOT / "out_grade"; out.mkdir(exist_ok=True)
D = json.load(open(S / "tagging/tag_data.json"))
EV = {json.load(open(f))["task"]: json.load(open(f)).get("evidence") for f in glob.glob(str(S / "train_tags/out/sonnet_tags/*.json"))}
AT = {json.loads(l)["task"]: json.loads(l) for l in open("/Users/aibasis/Benchmark_Research/Benchmark_research/docs/topics/router-benchmark/attribution_v2/deep_attribution_46.jsonl")}
fails = sorted(t for t, v in D.items() if v["passes"] < v["runs"])
passes = sorted(t for t, v in D.items() if v["passes"] == v["runs"])
rng = random.Random(20261116)
pairs = {}
for t in fails:
    same = [p for p in passes if D[p]["repo"] == D[t]["repo"]]
    pool = same if len(same) >= 2 else same + rng.sample([p for p in passes if p not in same], 2 - len(same))
    pairs[t] = rng.sample(pool, 2)
json.dump(pairs, open(ROOT / "pairs.json", "w"), indent=1)
def ev(t):
    e = EV.get(t) or []
    return "\n".join(f"- {x}" for x in (e if isinstance(e, list) else [e]))
def block(t, label):
    v = D[t]
    return (f"## {label}：{t}（DS {v['passes']}/{v['runs']} 次通过）\n### 题面\n{v['issue'][:3500]}\n"
            f"### 动手前在仓库里查到的线索\n{ev(t)}\n### 标准修复（只用于你理解差异）\n{v.get('gold','')[:3000]}\n")
PROMPT = """你在帮我们总结「DS 这个编程智能体在什么情况下会挂」的规律，要求这些规律在动手前（只看题面和仓库）就能判断。
下面有 1 道 DS 挂了的题，和 2 道同仓库（或相近）DS 做对了的题。{attr}
请找出能把「挂的这道」和「做对的两道」区分开的特征。要求：
1. 只写动手前就能从题面或仓库看出来的东西，不能依赖标准修复或测试本身。
2. 必须是挂的那道有、做对的两道没有（或明显更弱）。三道都有的风险不算，单独列在 shared_risks 里。
3. 写成可以推广到别的项目的规律，带上触发条件：「当……并且……时，DS 容易挂」。
只输出一行 JSON：{{"discriminating":[{{"feature":"规律（≤60字）","condition":"什么条件下才致命（≤60字）","visible_in":"题面/仓库"}}],"shared_risks":["三道都有、不能区分的风险（≤30字）"],"why_controls_passed":"一句话"}}

{blocks}"""
def one(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    a = AT.get(t)
    attr = f"挂的原因（阅卷记录）：{a['L1_what']}；过程：{a['L2_why']}。" if a else ""
    blocks = block(t, "挂了的题") + "\n".join(block(p, f"做对的题{i+1}") for i, p in enumerate(pairs[t]))
    p = subprocess.run(["claude", "-p", PROMPT.format(attr=attr, blocks=blocks), "--output-format", "json", "--model", model,
                        "--max-turns", "1", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=400)
    try:
        txt = json.loads(p.stdout).get("result", ""); dec = json.JSONDecoder()
        for i in reversed([k for k, c in enumerate(txt) if c == "{"]):
            try:
                obj, _ = dec.raw_decode(txt, i)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "discriminating" in obj:
                obj.update(task=t, controls=pairs[t], repo=D[t]["repo"])
                (out / f"{t}.json").write_text(json.dumps(obj, ensure_ascii=False) + "\n"); return t, "ok"
        raise ValueError("no json")
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:]); return t, "err"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, fails): print(t, s, flush=True)
