#!/usr/bin/env python3
"""经验卡对照（只判断，不读仓库）：题面 + Sonnet 冻结证据 → p_fail。
组别：E0 不给经验；E1 只给整体水平（卡片第一节）；E2 给完整经验卡。
用法：judge_exp.py <E0|E1|E2> <模型> <任务清单json> [--jobs N]"""
import sys, json, pathlib, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent
RB = ROOT.parent / "rebench"
arm, model, tl = sys.argv[1], sys.argv[2], sys.argv[3]
jobs = int(sys.argv[5]) if len(sys.argv) > 5 else 4
short = model.replace("claude-", "").replace("-5-5", "")
out = ROOT / "out" / f"{arm}_{short}"; out.mkdir(parents=True, exist_ok=True)
CARD = (ROOT / "ds_card_v2.md").read_text()
BASE = CARD.split("## 二、")[0]
EXTRA = {"E0": "", "E1": "\n===== 关于这个智能体的整体水平 =====\n" + BASE,
         "E2": "\n===== 关于这个智能体的经验卡 =====\n" + CARD}[arm]
PROMPT = """你是「动手前预测器」的判断环节。另一位调查员已经在仓库里查过这道题，下面是题面和它找到的证据（只有证据，没有它的结论）。
请只根据题面、这些证据{extra_hint}，判断编程智能体 DeepSeek 修好这道题并通过维护者隐藏测试的难度，给出失败概率。不要使用对上游修法的记忆。
请列出影响难度的主要因素（每条说明方向和分量），再给出失败概率。只输出一行 JSON：{{"task":"{task}","factors":[{{"factor":"影响难度的因素（≤20字）","direction":"更难/更容易","weight":"大/中/小"}}],"main_reason":"一句话说清最关键的判断依据（≤60字）","p_fail":0~1}}
{extra}
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
    r = json.load(open(RB / "out/sonnet_gen" / f"{t}.json"))
    ev = r.get("evidence") or []
    ev = "\n".join(f"- {e}" for e in (ev if isinstance(ev, list) else [ev]))
    prompt = PROMPT.format(task=t, extra=EXTRA, extra_hint=("" if arm == "E0" else "和下面关于这个智能体的资料"),
                           issue=(RB / "issue" / f"{t}.md").read_text()[:6000], evidence=ev)
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        row = extract(json.loads(p.stdout).get("result", "")); row["task"] = t
        (out / f"{t}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n"); return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:]); return t, "err"
tasks = json.load(open(tl))
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, tasks): print(t, s, flush=True)
