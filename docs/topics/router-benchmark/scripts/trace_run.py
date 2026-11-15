#!/usr/bin/env python3
"""与 run_predictor 同一提示/同一快照，但用 stream-json 完整记录轨迹。用法：trace_run.py <tag> <task,...> [--jobs N]"""
import sys, os, json, pathlib, subprocess, concurrent.futures as cf
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import run_predictor as rp
ROOT = pathlib.Path(__file__).resolve().parent
tag, tasks = sys.argv[1], sys.argv[2].split(",")
jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 3
out = ROOT / "out_trace" / tag; out.mkdir(parents=True, exist_ok=True)
def one(t):
    if (out / f"{t}.jsonl").exists(): return t, "skip"
    prompt = rp.TEMPLATE.format(task=t, check=rp.CHECK, issue=(ROOT / "issue" / f"{t}.md").read_text())
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "stream-json", "--verbose", "--allowedTools", rp.TOOLS,
                        "--disallowedTools", "WebFetch,WebSearch,Edit,Write,Agent", "--max-turns", "60",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands"],
                       cwd=ROOT / "snap" / t, env=dict(os.environ), capture_output=True, text=True, timeout=1800)
    (out / f"{t}.jsonl").write_text(p.stdout)
    return t, "ok" if '"type":"result"' in p.stdout else "noresult"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, tasks): print(t, s, flush=True)
