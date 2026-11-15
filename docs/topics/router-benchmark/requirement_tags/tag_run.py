#!/usr/bin/env python3
"""任务需求标注（一题一次 claude -p 调用，无工具）。
用法：python3 tag_run.py <mode: open|fixed> <tag> <tasks.json> [--model M] [--jobs N] [--vocab vocab.md]
  open：自由写需求短语（用来长出词表）；fixed：按冻结词表多标签打分。
输入数据 tag_data.json（题面、标准答案补丁、测试补丁）。只看任务本身，不看 DS 结果。"""
import argparse, concurrent.futures as cf, json, os, pathlib, re, subprocess

ROOT = pathlib.Path(__file__).resolve().parent
DATA = json.load(open(ROOT / "tag_data.json"))
OPEN = """你是代码任务分析员。下面是一个开源仓库的问题（issue）、维护者的正确修复（gold patch）和用来验收的测试（test patch）。
请回答：**正确完成这道题，本身需要做到哪些事**（与谁来做无关）。写成 3~6 条「需求短语」，要求：
- 通用、可跨仓库复用（不要写仓库专有名词），每条 ≤20 字，例如「改动多处并列实现」「处理阈值边界(>=)」「精确匹配报错文案」「新增公开参数」「解析多种日期格式」；
- 只写测试真正检查到的需求；
- 每条附一句证据（测试名或补丁里的函数）。
只输出一行 JSON：{{"task":"{task}","requirements":[{{"req":"...","evidence":"..."}}]}}

===== issue =====
{issue}
===== gold patch =====
{gold}
===== test patch =====
{test}
"""
FIXED = """你是代码任务分析员。下面是一个开源仓库的问题（issue）、维护者的正确修复（gold patch）和验收测试（test patch）。
按下面的固定词表，判断**正确完成这道题本身需要哪些能力**（与谁来做无关）。每个单元给 0/1，只在测试真正检查到时给 1；并为每个给 1 的单元写一句证据。
词表：
{vocab}
只输出一行 JSON：{{"task":"{task}","units":{{"<单元ID>":0或1,...全部单元都要给}},"evidence":{{"<单元ID>":"..."}}}}

===== issue =====
{issue}
===== gold patch =====
{gold}
===== test patch =====
{test}
"""


def extract(text):
    dec = json.JSONDecoder()
    fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
    for src in (text, fixed):
        for i in reversed([k for k, c in enumerate(src) if c == "{"]):
            try:
                obj, _ = dec.raw_decode(src, i)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "task" in obj:
                return obj
    raise ValueError("no json")


def one(mode, tag, task, model, vocab):
    out = ROOT / "out" / tag
    out.mkdir(parents=True, exist_ok=True)
    if (out / f"{task}.json").exists():
        return task, "skip"
    d = DATA[task]
    tpl = OPEN if mode == "open" else FIXED
    prompt = tpl.format(task=task, issue=d["issue"], gold=d["gold"], test=d["test"], vocab=vocab)
    env = dict(os.environ)
    try:
        p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--model", model, "--max-turns", "1",
                            "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
                            "--disallowedTools", "Bash,Read,Grep,Glob,Edit,Write,WebFetch,WebSearch,Agent"],
                           cwd="/tmp", env=env, capture_output=True, text=True, timeout=600)
        row = extract(json.loads(p.stdout).get("result", ""))
        row["task"] = task
        (out / f"{task}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n")
        return task, "ok"
    except Exception as e:
        (out / f"{task}.err").write_text(f"{type(e).__name__}: {e}\n{locals().get('p').stdout[-2000:] if locals().get('p') else ''}")
        return task, "err"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode"); ap.add_argument("tag"); ap.add_argument("tasks")
    ap.add_argument("--model", default="claude-sonnet-5-5"); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--vocab")
    a = ap.parse_args()
    vocab = open(a.vocab).read() if a.vocab else ""
    tasks = json.load(open(a.tasks))
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for t, s in ex.map(lambda t: one(a.mode, a.tag, t, a.model, vocab), tasks):
            print(t, s, flush=True)
