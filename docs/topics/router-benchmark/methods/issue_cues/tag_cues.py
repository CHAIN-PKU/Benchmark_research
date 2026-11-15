#!/usr/bin/env python3
"""盲打题面特征：只给题面，按 cue_vocab_v1.md 打 C01..C12 的 0/1。
用法：tag_cues.py <模型> <输出tag> [--jobs N]"""
import sys, json, pathlib, subprocess, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent
model, tag = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 4
out = ROOT / "out_tag" / tag; out.mkdir(parents=True, exist_ok=True)
rows = json.load(open(ROOT / "dl/ml_rows.json"))
VOCAB = (ROOT / "cue_vocab_v1.md").read_text()
KEYS = [f"C{i:02d}" for i in range(1, 13)]
PROMPT = """{vocab}

下面是一道仓库任务的题面。只根据题面文字判断每条特征有没有（有=1，没有=0），不要猜测代码或答案。
只输出一行 JSON：{{"C01":0或1, ..., "C12":0或1}}，12 个键都要有。

===== 题面 =====
{issue}
"""
def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and all(k in obj for k in KEYS):
            return {k: int(obj[k]) for k in KEYS}
    raise ValueError("no json")
def one(r):
    t = r["instance_id"]
    if (out / f"{t}.json").exists(): return t, "skip"
    p = subprocess.run(["claude", "-p", PROMPT.format(vocab=VOCAB, issue=r["problem_statement"][:6000]),
                        "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        row = extract(json.loads(p.stdout).get("result", "")); row["task"] = t
        (out / f"{t}.json").write_text(json.dumps(row) + "\n"); return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:]); return t, "err"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, rows): print(t, s, flush=True)
