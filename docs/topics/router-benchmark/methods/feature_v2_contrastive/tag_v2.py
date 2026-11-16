#!/usr/bin/env python3
"""按 feature_vocab_v2.md 给题打 V01..V13（0/1）。输入：题面 + 动手前线索（sonnet_tags 组冻结 evidence，旧题与前瞻同一提示词）。
用法：tag_v2.py <old|prosp> <模型> [--jobs N]"""
import sys, json, pathlib, subprocess, glob, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
split, model = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 6
out = ROOT / "out_tag" / split; out.mkdir(parents=True, exist_ok=True)
VOCAB = (ROOT / "feature_vocab_v2.md").read_text()
K = [f"V{i:02d}" for i in range(1, 14)]
if split == "old":
    D = json.load(open(S / "tagging/tag_data.json")); ISS = {t: v["issue"] for t, v in D.items()}
    EVD = S / "train_tags/out/sonnet_tags"
else:
    ISS = {pathlib.Path(f).stem: open(f).read() for f in glob.glob(str(S / "prosp/issue/*.md"))}
    EVD = S / "prosp/out/sonnet_tags"
PROMPT = """{vocab}

下面是一道仓库任务的题面，以及动手前在仓库里查到的线索。只根据这些信息，判断 13 条特征各自有没有（有=1，没有=0）。不要猜测标准答案。
只输出一行 JSON：{{"V01":0或1, ..., "V13":0或1}}，13 个键都要有。

===== 题面 =====
{issue}
===== 动手前查到的线索 =====
{ev}
"""
def one(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    f = EVD / f"{t}.json"
    e = json.load(open(f)).get("evidence") if f.exists() else []
    e = "\n".join(f"- {x}" for x in (e if isinstance(e, list) else [e])) or "（无）"
    p = subprocess.run(["claude", "-p", PROMPT.format(vocab=VOCAB, issue=ISS[t][:6000], ev=e), "--output-format", "json",
                        "--model", model, "--max-turns", "1", "--setting-sources", "", "--strict-mcp-config",
                        "--disable-slash-commands", "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=300)
    try:
        txt = json.loads(p.stdout).get("result", ""); dec = json.JSONDecoder()
        for i in reversed([k for k, c in enumerate(txt) if c == "{"]):
            try:
                obj, _ = dec.raw_decode(txt, i)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and all(k in obj for k in K):
                row = {k: int(obj[k]) for k in K}; row["task"] = t
                (out / f"{t}.json").write_text(json.dumps(row) + "\n"); return t, "ok"
        raise ValueError("no json")
    except Exception as ex:
        (out / f"{t}.err").write_text(str(ex) + "\n" + p.stdout[-1500:]); return t, "err"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, sorted(ISS)): print(t, s, flush=True)
