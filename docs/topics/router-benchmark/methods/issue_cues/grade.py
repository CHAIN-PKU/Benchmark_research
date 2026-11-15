#!/usr/bin/env python3
"""阅卷：对公开智能体在总结集上的失败做事后归因（只用于总结特征，不参与任何预测）。
用法：grade.py <模型> [--jobs N]
输入：grade_cases.json、dl/ml_rows.json；首次运行时从公开 S3 下载该智能体的补丁与评测报告到 dl/sub/。"""
import sys, json, pathlib, subprocess, urllib.request, concurrent.futures as cf, glob, os
ROOT = pathlib.Path(__file__).resolve().parent
model = sys.argv[1]; jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 4
out = ROOT / "out_grade"; out.mkdir(exist_ok=True)
rows = {r["instance_id"]: r for r in json.load(open(ROOT / "dl/ml_rows.json"))}
cases = json.load(open(ROOT / "grade_cases.json"))
GUIDE = (ROOT / "grade_prompt.md").read_text()
S3 = "https://swe-bench-submissions.s3.amazonaws.com/multilingual"
SUBDIR = {os.path.basename(f)[3:-5] for f in glob.glob(str(ROOT.parent / "pubhist/ml_*.json"))}

def fetch(agent, t):
    d = ROOT / "dl/sub" / agent / t; d.mkdir(parents=True, exist_ok=True)
    tj, rj = d / "traj.json", d / "report.json"
    if not tj.exists():
        urllib.request.urlretrieve(f"{S3}/{agent}/trajs/{t}/{t}.traj.json", tj)
    if not rj.exists():
        urllib.request.urlretrieve(f"{S3}/{agent}/logs/{t}/report.json", rj)
    sub = json.load(open(tj)).get("info", {}).get("submission") or ""
    rep = json.load(open(rj)).get(t, {})
    return sub, rep

def extract(text):
    dec = json.JSONDecoder()
    for i in reversed([k for k, c in enumerate(text) if c == "{"]):
        try:
            obj, _ = dec.raw_decode(text, i)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "cause_type" in obj:
            return obj
    raise ValueError("no json")

def one(c):
    t, a = c["task"], c["agent"]; key = f"{t}__{a}"
    if (out / f"{key}.json").exists(): return key, "skip"
    try:
        sub, rep = fetch(a, t)
    except Exception as e:
        (out / f"{key}.err").write_text(f"fetch {e}"); return key, "err"
    r = rows[t]; ts = rep.get("tests_status", {})
    failed = {k: v.get("failure", []) for k, v in ts.items() if v.get("failure")}
    n_other = round(c["others_pass"] * 14)
    prompt = (GUIDE + f"\n\n===== 题面 =====\n{r['problem_statement'][:6000]}\n"
              f"===== 维护者标准修复 =====\n{r['patch'][:8000]}\n"
              f"===== 维护者隐藏测试 =====\n{r['test_patch'][:8000]}\n"
              f"===== 该智能体提交的补丁 =====\n{(sub or '（空补丁）')[:8000]}\n"
              f"===== 评测结果：未通过的测试 =====\n{json.dumps(failed, ensure_ascii=False)[:2000]}\n"
              f"补丁能否应用：{rep.get('patch_successfully_applied')}\n"
              f"===== 同题其他智能体 =====\n14 个智能体中约 {n_other} 个做对。\n")
    p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                        "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                       cwd="/tmp", capture_output=True, text=True, timeout=400)
    try:
        row = extract(json.loads(p.stdout).get("result", ""))
        row.update(task=t, agent=a, kind=c["kind"], others_pass=c["others_pass"])
        (out / f"{key}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n"); return key, "ok"
    except Exception as e:
        (out / f"{key}.err").write_text(str(e) + "\n" + p.stdout[-1500:] + p.stderr[-500:]); return key, "err"

if __name__ == "__main__":
    sel = cases[:int(os.environ.get("N", len(cases)))]
    with cf.ThreadPoolExecutor(jobs) as ex:
        for k, s in ex.map(one, sel): print(k, s, flush=True)
