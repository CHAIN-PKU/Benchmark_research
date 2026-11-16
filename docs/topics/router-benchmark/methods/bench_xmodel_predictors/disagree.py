#!/usr/bin/env python3
"""同题同输入：Sonnet 判对、DS/GLM 判错的题，逐题看弱预测者错在哪（查 / 掂量 / 被无关风险吓到 / 尺度）。
选题：按与 14 家公开难度的秩误差，弱者误差大且 Sonnet 误差小的前 12 道（每个弱者）。分析用 Sonnet。"""
import json, glob, os, sys, subprocess, concurrent.futures as cf, numpy as np
from scipy.stats import rankdata
S = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); X = f"{S}/xmodel"
D = json.load(open(f"{S}/tagging/tag_data.json")); subs = [json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
AT = {json.loads(l)["task"]: json.loads(l) for l in open(os.path.expanduser("~/Benchmark_Research/Benchmark_research/docs/topics/router-benchmark/attribution_v2/deep_attribution_46.jsonl"))}
def load(m):
    R = {}
    for f in glob.glob(f"{X}/out/{m}/*.json"):
        try: r = json.load(open(f)); float(r["p_fail"]); r.pop("_usage", None); R[r["task"]] = r
        except Exception: pass
    return R
M = {m: load(m) for m in ("sonnet_ref", "ds", "glm")}
ts = sorted(t for t in set.intersection(*[set(v) for v in M.values()]) if t in D and all(t in s for s in subs))
diff = {t: np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts}
rk = lambda m: dict(zip(ts, rankdata([M[m][t]["p_fail"] for t in ts]) / len(ts)))
rd = dict(zip(ts, rankdata([diff[t] for t in ts]) / len(ts))); RS = rk("sonnet_ref")
P = """同一道真实仓库题、同一份修复前代码和同一份清单，两个「动手前预测者」各自读仓库后给出了风险判断。事后真实结果见下。预测者 A 判得比较准，预测者 B 判得明显不准。
请分析 B 错在哪，只能从下面四类里选主因（可附次因）：
- 没查到：B 的证据里根本没有 A 抓到的关键风险
- 查到了没掂量对：B 的证据里有那个关键风险，但给的分或概率与之不相称
- 被无关风险带偏：B 抓到了实际上不要紧的风险并据此高估，或因为某个看起来简单的表象而低估
- 尺度：B 的相对排序其实对，只是整体偏高或偏低
只输出一行 JSON：{{"main":"没查到|查到了没掂量对|被无关风险带偏|尺度","second":"同上或空","key_risk":"真正决定成败的那个点（≤50字）","b_mistake":"B 具体错在哪（≤60字）"}}

===== 题面（节选）=====
{issue}
===== 真实结果 =====
14 家公开编程智能体中 {nf}/14 家没做对（{lvl}）；DeepSeek 自己的结果：{ds}{at}
===== 预测者 A =====
{a}
===== 预测者 B =====
{b}"""
def claude(prompt):
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", "claude-sonnet-5-5", "--max-turns", "1", "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"], cwd="/tmp", capture_output=True, text=True, timeout=400)
    txt = json.loads(p.stdout).get("result", ""); dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(txt) if c == "{"]):
        try: o, _ = dec.raw_decode(txt, i)
        except json.JSONDecodeError: continue
        if "main" in o: return o
    raise ValueError(txt[-200:])
out = f"{X}/out_disagree"; os.makedirs(out, exist_ok=True)
jobs = []
for m in ("ds", "glm"):
    R = rk(m); sc = sorted(ts, key=lambda t: -(abs(R[t] - rd[t]) - abs(RS[t] - rd[t])))[:12]
    jobs += [(m, t) for t in sc]
def f(job):
    m, t = job; fn = f"{out}/{m}__{t}.json"
    if os.path.exists(fn): return job, "skip"
    nf = round(diff[t] * 14); a = AT.get(t)
    at = f"\n阅卷：{str(a['L1_what'])[:600]}" if a and D[t]["passes"] < D[t]["runs"] else ""
    fmt = lambda r: json.dumps({k: r[k] for k in ("risk_hidden", "risk_narrow", "risk_sibling", "p_fail", "evidence") if k in r}, ensure_ascii=False)
    try:
        r = claude(P.format(issue=D[t]["issue"][:2500], nf=nf, lvl="难" if nf >= 7 else "易" if nf <= 3 else "中", ds=f"{D[t]['passes']}/{D[t]['runs']} 次通过", at=at, a=fmt(M["sonnet_ref"][t]), b=fmt(M[m][t])))
    except Exception as e: return job, f"err {e}"
    r.update(model=m, task=t, b_p=M[m][t]["p_fail"], a_p=M["sonnet_ref"][t]["p_fail"], pub_fail=nf)
    open(fn, "w").write(json.dumps(r, ensure_ascii=False)); return job, "ok"
with cf.ThreadPoolExecutor(4) as ex:
    for j, s in ex.map(f, jobs): print(j, s, flush=True)
