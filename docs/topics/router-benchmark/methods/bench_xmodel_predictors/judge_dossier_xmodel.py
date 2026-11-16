#!/usr/bin/env python3
"""方法章「查证与判断分离」：同一份 Sonnet 写的仓库档案，换便宜模型（DS/GLM/Kimi）当判断者。
提示与 prereg_rebench_target 的 blind 组逐字相同（不告诉执行者是谁），可直接和 Sonnet blind 组比。
用法：python3 judge_dossier_xmodel.py <tag> <档案目录> <题面目录> [--jobs 4]
  档案目录 = prereg_rebench_target/out_dossier_rb（<task>.md）；题面目录 = rebench issue（<task>.md）
模型通道由环境变量指定（同 run_predictor.py）。输出 out_dosjudge/<tag>/<task>.json。不含答案标签、不读写令牌。"""
import sys, json, os, pathlib, shutil, subprocess, tempfile, concurrent.futures as cf
tag, ddir, idir = sys.argv[1], pathlib.Path(sys.argv[2]), pathlib.Path(sys.argv[3])
jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
out = pathlib.Path.cwd() / "out_dosjudge" / tag; out.mkdir(parents=True, exist_ok=True)
JUDGE = """判断{agent}修好下面这道新题、并通过维护者隐藏测试的可能性。不要使用对上游修法的记忆。

===== 新题：完整题面 =====
{issue}
===== 新题：动手前仓库档案 =====
{dos}

只输出一行 JSON：{{"p_fail":0~1,"reason":"一句话（≤60字）"}}"""
AGENT = "一个编程智能体（不告诉你是哪个模型）"
def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try: obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError: continue
        if isinstance(obj, dict) and "p_fail" in obj: return obj
    raise ValueError("no json")
def f(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    prompt = JUDGE.format(agent=AGENT, issue=(idir / f"{t}.md").read_text()[:6000], dos=(ddir / f"{t}.md").read_text())
    home = tempfile.mkdtemp(prefix=f"dj_{tag}_"); env = dict(os.environ); env["HOME"] = home
    try:
        p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--max-turns", "1",
                            "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                           cwd=home, env=env, capture_output=True, text=True, timeout=600)
        r = extract(json.loads(p.stdout).get("result", "")); r["task"] = t
        (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(f"{type(e).__name__}: {e}\n"); return t, "err"
    finally:
        shutil.rmtree(home, ignore_errors=True)
TS = sorted(p.stem for p in ddir.glob("*.md") if (idir / f"{p.stem}.md").exists())
if "--smoke" in sys.argv: TS = TS[:1]
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(f, TS): print(t, s, flush=True)
