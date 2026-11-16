#!/usr/bin/env python3
"""带做题者身份的预测（只判断，不读仓库）：同一份 Sonnet 冻结证据，分别告诉判断者做题的是 DS 或 GLM。
用法：judge_target.py <DS|GLM> <模型> [--jobs N]；题单 = pj/ns_judge.json（预注册 77 道）"""
import sys, json, pathlib, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent
PJ = ROOT.parent / "pj"
tgt, model = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 4
out = ROOT / "out" / f"{tgt}_{model.replace('claude-','').replace('-5-5','')}"; out.mkdir(parents=True, exist_ok=True)
PROFILE = {
 "DS": "做题的智能体是 DeepSeek v4.1 flash（便宜的开源模型）。在这类真实仓库任务上，它大约 75%~80% 能做对。",
 "GLM": "做题的智能体是 GLM 5.3x Flash（便宜的开源模型，比 DeepSeek v4.1 flash 更弱一些）。在这类真实仓库任务上，同级别的 GLM 模型公开成绩大约 65%~70% 能做对。",
}[tgt]
PROMPT = """你是「动手前预测器」的判断环节。另一位调查员已经在仓库里查过这道题，下面是题面和它找到的证据（只有证据，没有它的结论）。
{profile}
请只根据题面、证据和上面关于做题者的信息，判断这个智能体修好这道题并通过维护者隐藏测试的难度，给出失败概率。不要使用对上游修法的记忆。
只输出一行 JSON：{{"task":"{task}","main_reason":"一句话（≤60字）","p_fail":0~1}}

===== 题面 =====
{issue}
===== 调查员找到的证据 =====
{evidence}
"""
def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "p_fail" in obj:
            return obj
    raise ValueError("no json")
def one(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    r = json.load(open(PJ / "out/sonnet_gen" / f"{t}.json"))
    ev = r.get("evidence") or []
    ev = "\n".join(f"- {e}" for e in (ev if isinstance(ev, list) else [ev]))
    prompt = PROMPT.format(profile=PROFILE, task=t, issue=(PJ / "issue" / f"{t}.md").read_text()[:6000], evidence=ev)
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        row = extract(json.loads(p.stdout).get("result", "")); row["task"] = t
        (out / f"{t}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n"); return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:]); return t, "err"
tasks = json.load(open(PJ / "ns_judge.json"))
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, tasks): print(t, s, flush=True)
