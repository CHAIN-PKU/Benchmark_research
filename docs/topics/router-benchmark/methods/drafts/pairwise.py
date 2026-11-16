#!/usr/bin/env python3
"""两两比较判断：给判断者两道题的题面+动手前线索，只问「哪道 DS 更可能挂」。汇总成排序（Bradley-Terry）。
同时提供逐题打分对照（pointwise），两者用同一份线索。只用旧题 186 道（sonnet_tags 冻结线索）。
用法：pairwise.py <pair|point> <模型> [--jobs N] ；配对表 pairs.json 由 make_pairs() 固定种子生成"""
import sys, json, pathlib, random, subprocess, glob, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
mode, model = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 6
short = model.replace("claude-", "").replace("-5-5", "")
out = ROOT / "out" / f"{mode}_{short}"; out.mkdir(parents=True, exist_ok=True)
D = json.load(open(S / "tagging/tag_data.json"))
EV = {json.load(open(f))["task"]: json.load(open(f)).get("evidence") for f in glob.glob(str(S / "train_tags/out/sonnet_tags/*.json"))}
TS = sorted(t for t in D if t in EV)
def make_pairs(k=6, seed=20261116):
    rng = random.Random(seed); pairs = set()
    for t in TS:
        others = [o for o in TS if o != t]
        for o in rng.sample(others, k // 2):
            pairs.add(tuple(sorted((t, o))))
    pairs = sorted(pairs); rng.shuffle(pairs)
    return [list(p) if rng.random() < 0.5 else [p[1], p[0]] for p in pairs]   # 随机左右顺序，避免位置偏差
PF = ROOT / "pairs.json"
if not PF.exists(): json.dump(make_pairs(), open(PF, "w"))
PAIRS = json.load(open(PF))
AGENT = "编程智能体 DeepSeek（它习惯照题面实现、通常只为题面给的例子写自测）"
def ev(t):
    e = EV.get(t) or []
    return "\n".join(f"- {x}" for x in (e if isinstance(e, list) else [e]))
def blk(t, name): return f"===== 题 {name} =====\n【题面】\n{D[t]['issue'][:3000]}\n【动手前在仓库里查到的线索】\n{ev(t)}\n"
P_PAIR = """下面是两道真实仓库任务，各附题面和动手前在仓库里查到的线索（不含任何答案）。
请判断：{agent}修这两道题时，哪一道更可能失败（没通过维护者的隐藏测试）？不要使用对上游修法的记忆。
只输出一行 JSON：{{"harder":"A"或"B","confidence":"高/中/低","reason":"一句话（≤50字）"}}

{a}
{b}"""
P_POINT = """下面是一道真实仓库任务的题面和动手前在仓库里查到的线索（不含任何答案）。
请判断{agent}修这道题失败（没通过维护者的隐藏测试）的概率。不要使用对上游修法的记忆。
只输出一行 JSON：{{"p_fail":0~1,"reason":"一句话（≤50字）"}}

{a}"""
def call(prompt, need):
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    txt = json.loads(p.stdout).get("result", ""); dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(txt) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(txt, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and need in obj: return obj
    raise ValueError("no json: " + txt[-300:])
def one(item):
    if mode == "pair":
        a, b = item; key = f"{a}__VS__{b}"
        if (out / f"{key}.json").exists(): return key, "skip"
        try:
            r = call(P_PAIR.format(agent=AGENT, a=blk(a, "A"), b=blk(b, "B")), "harder"); r.update(A=a, B=b)
        except Exception as e:
            (out / f"{key}.err").write_text(str(e)); return key, "err"
    else:
        key = item
        if (out / f"{key}.json").exists(): return key, "skip"
        try:
            r = call(P_POINT.format(agent=AGENT, a=blk(item, "")), "p_fail"); r["task"] = item
        except Exception as e:
            (out / f"{key}.err").write_text(str(e)); return key, "err"
    (out / f"{key}.json").write_text(json.dumps(r, ensure_ascii=False) + "\n"); return key, "ok"
if __name__ == "__main__":
    items = PAIRS if mode == "pair" else TS
    if "--dry" in sys.argv: print(len(TS), "tasks", len(PAIRS), "pairs"); sys.exit()
    with cf.ThreadPoolExecutor(jobs) as ex:
        for k, s in ex.map(one, items): print(k, s, flush=True)
