#!/usr/bin/env python3
"""参照式判断：新题（题面+动手前线索）+ 6 个历史案例（3 挂 3 过，只取另一折仓库）→ 失败概率。
组别：none 不给案例；rand 随机案例；sim 按「难点本质」相似挑案例（字符 n-gram TF-IDF，余弦）。
用法：judge.py <none|rand|sim> <模型> [--jobs N]"""
import sys, json, pathlib, glob, random, subprocess, concurrent.futures as cf
import numpy as np
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
arm, model = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 6
short = model.replace("claude-", "").replace("-5-5", "")
out = ROOT / "out_judge" / f"{arm}_{short}"; out.mkdir(parents=True, exist_ok=True)
D = json.load(open(S / "tagging/tag_data.json")); FOLD = json.load(open(ROOT / "repo_fold.json"))
EV = {json.load(open(f))["task"]: json.load(open(f)).get("evidence") for f in glob.glob(str(S / "train_tags/out/sonnet_tags/*.json"))}
CARD = {json.load(open(f))["task"]: json.load(open(f)) for f in glob.glob(str(ROOT / "out_card/*.json"))}
QRY = {json.load(open(f))["task"]: json.load(open(f))["core"] for f in glob.glob(str(ROOT / "out_query/*.json"))}
TS = sorted(t for t in D if t in EV and t in CARD and t in QRY)
fail = lambda t: D[t]["passes"] < D[t]["runs"]
fold = lambda t: FOLD[D[t]["repo"]]
def ngrams(s, n=(2, 3)): return [s[i:i + k] for k in n for i in range(len(s) - k + 1)]
VOC = {}
def vec(s):
    v = {}
    for g in ngrams(s): v[g] = v.get(g, 0) + 1
    return v
DF = {}
for t in TS:
    for g in set(ngrams(CARD[t]["core"])): DF[g] = DF.get(g, 0) + 1
N = len(TS)
def tfidf(s):
    v = vec(s); w = {g: c * np.log((N + 1) / (DF.get(g, 0) + 1)) for g, c in v.items()}
    n = np.sqrt(sum(x * x for x in w.values())) or 1.0
    return {g: x / n for g, x in w.items()}
LIB = {t: tfidf(CARD[t]["core"]) for t in TS}
def cos(a, b): return sum(x * b.get(g, 0) for g, x in a.items())
def anchors(t):
    pool = [o for o in TS if fold(o) != fold(t)]
    F = [o for o in pool if fail(o)]; P = [o for o in pool if not fail(o)]
    if arm == "rand":
        rng = random.Random(t); return rng.sample(F, 3) + rng.sample(P, 3)
    q = tfidf(QRY[t])
    top = lambda L: sorted(L, key=lambda o: -cos(q, LIB[o]))[:3]
    return top(F) + top(P)
def ev(t):
    e = EV.get(t) or []
    return "\n".join(f"- {x}" for x in (e if isinstance(e, list) else [e]))
AGENT = "编程智能体 DeepSeek（它习惯照题面实现、通常只为题面给的例子写自测）"
HEAD = """判断{agent}修好下面这道新题、并通过维护者隐藏测试的可能性。不要使用对上游修法的记忆。
{refs}
===== 新题 =====
【题面】
{issue}
【动手前在仓库里查到的线索】
{ev}

只输出一行 JSON：{{{rank}"p_fail":0~1,"reason":"一句话（≤60字）"}}"""
def refs_text(A):
    rng = random.Random(len(A)); A = A[:]; rng.shuffle(A)
    lines = ["===== 参照：这个智能体以前做过的 6 道题（真实结果）=====",
             "请先把新题和这些案例逐一比较：新题比哪些更难、比哪些更容易，再据此给出失败概率。"]
    for i, o in enumerate(A, 1):
        c = CARD[o]; res = "失败" if fail(o) else "做对"
        lines.append(f"案例{i}【{res}，{D[o]['passes']}/{D[o]['runs']} 次通过】难点：{c['core']}；动手前线索：{'；'.join(c.get('cues', []))}；原因：{c['verdict_reason']}")
    return "\n".join(lines) + "\n"
def one(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    A = [] if arm == "none" else anchors(t)
    prompt = HEAD.format(agent=AGENT, refs=refs_text(A) if A else "", issue=D[t]["issue"][:3500], ev=ev(t),
                         rank='"harder_than":[比新题容易的案例编号],"easier_than":[比新题难的案例编号],' if A else "")
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
            if isinstance(obj, dict) and "p_fail" in obj:
                obj.update(task=t, anchors=A); (out / f"{t}.json").write_text(json.dumps(obj, ensure_ascii=False) + "\n"); return t, "ok"
        raise ValueError("no json")
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-800:]); return t, "err"
if __name__ == "__main__":
    with cf.ThreadPoolExecutor(jobs) as ex:
        for t, s in ex.map(one, TS): print(t, s, flush=True)
