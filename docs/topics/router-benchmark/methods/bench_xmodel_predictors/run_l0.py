#!/usr/bin/env python3
"""第 4 章 L0 档：只给题面、不给仓库（不开任何工具），只换预测者模型。
放在 predictor_xmodel/ 目录下运行（读 issue/<task>.md 与 tasks.json），模型通道与 run_predictor.py 一样由环境变量指定。
输出：out_l0/<tag>/<task>.json；本脚本不读、不写、不打印任何令牌，不含答案标签。
用法：python3 run_l0.py <tag> [--tasks a,b] [--jobs 4]"""
import argparse, concurrent.futures as cf, json, os, pathlib, re, shutil, subprocess, tempfile, time
ROOT = pathlib.Path.cwd()
TEMPLATE = """你是研究中的「动手前预测器」。下面是一个开源仓库的题面（issue）。一个编程智能体（DeepSeek）稍后会尝试修复它，维护者有隐藏测试。
你看不到仓库代码，只能根据题面判断。不要使用对上游修法的记忆。只输出一行 JSON，不要输出其他内容：
{{"task":"{task}","p_fail":0~1,"reason":"一句话（≤60字）"}}

===== 题面 =====
{issue}
"""
def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try: obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError: continue
        if isinstance(obj, dict) and "p_fail" in obj: return obj
    raise ValueError("no JSON object with p_fail")
def one(tag, task, timeout):
    out = ROOT / "out_l0" / tag; out.mkdir(parents=True, exist_ok=True)
    if (out / f"{task}.json").exists(): return task, "skip"
    prompt = TEMPLATE.format(task=task, issue=(ROOT / "issue" / f"{task}.md").read_text()[:8000])
    home = tempfile.mkdtemp(prefix=f"l0_{tag}_"); env = dict(os.environ); env["HOME"] = home
    t0 = time.time()
    try:
        p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--max-turns", "1",
                            "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                           cwd=home, env=env, capture_output=True, text=True, timeout=timeout)
        res = json.loads(p.stdout); row = extract(res.get("result", ""))
        row.update(task=task, _secs=round(time.time() - t0), _usage=res.get("usage"))
        (out / f"{task}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n"); return task, "ok"
    except Exception as e:
        (out / f"{task}.err").write_text(f"{type(e).__name__}: {e}\n"); return task, "err"
    finally:
        shutil.rmtree(home, ignore_errors=True)
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("tag"); ap.add_argument("--tasks"); ap.add_argument("--jobs", type=int, default=4); ap.add_argument("--timeout", type=int, default=600)
    a = ap.parse_args(); tasks = a.tasks.split(",") if a.tasks else json.load(open(ROOT / "tasks.json"))
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for t, s in ex.map(lambda t: one(a.tag, t, a.timeout), tasks): print(t, s, flush=True)
