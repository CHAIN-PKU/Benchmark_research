#!/usr/bin/env python3
"""方法 v4 第一步：为每道题建「仓库档案」（只看题面 + 修复前快照，不看答案）。
查证 AI 围绕「这道题最可能难在哪」系统查证，输出结构化档案（约 3000 字以内），不给概率。
用法：build_dossier.py <任务清单json> <模型> [--jobs N]"""
import sys, os, re, json, pathlib, subprocess, time, concurrent.futures as cf
ROOT = pathlib.Path(__file__).resolve().parent; S = ROOT.parent
tl, model = sys.argv[1], sys.argv[2]; jobs = int(sys.argv[4]) if len(sys.argv) > 4 else 3
out = ROOT / "out_dossier"; out.mkdir(exist_ok=True)
D = json.load(open(S / "tagging/tag_data.json"))
TOOLS = "Read,Grep,Glob,Bash(grep:*),Bash(sed:*),Bash(ls:*),Bash(find:*),Bash(cat:*),Bash(head:*),Bash(wc:*)"
PROMPT = """当前目录是一个开源仓库在修复前的代码快照（只读）。下面是一道 issue，稍后会有一个编程智能体来修，维护者有隐藏测试。
你的任务不是修，也不是打分，而是为「判断这道题难不难」整理一份仓库档案。请在仓库里认真查证（至少 10 次搜索/阅读），然后按下面的格式输出档案，总长不超过 2500 字。不要使用你对上游当年怎么修的记忆。

【1 题面要点】要求的行为是什么；题面是否给了复现、期望输出、修法建议（照抄关键句）。
【2 相关代码】最可能要改的文件和函数（文件:行号），各自负责什么。
【3 并列与牵连】有没有需要同样改动的并列实现、成对方法、多个调用点；改这里还会影响哪些地方。
【4 现有测试与约定】现有测试怎么断言相关行为（文件:行号，引用断言）；仓库里有没有约定、参考实现或外部规范决定了正确行为；与题面期望是否冲突。
【5 边界与隐含要求】题面没写、但正确实现很可能要处理的情况。
【6 改动规模】大概要改几个文件、几处；是局部修补还是要新增结构或贯穿多层。
【7 难点一句话】这道题最可能难在哪。

===== issue =====
{issue}
"""
def one(t):
    if (out / f"{t}.md").exists(): return t, "skip"
    snap = S / "train_tags/snap" / t
    t0 = time.time()
    p = subprocess.run(["claude", "-p", PROMPT.format(issue=D[t]["issue"][:6000]), "--output-format", "json", "--model", model,
                        "--allowedTools", TOOLS, "--disallowedTools", "WebFetch,WebSearch,Edit,Write,Agent", "--max-turns", "40",
                        "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands"],
                       cwd=snap, capture_output=True, text=True, timeout=1200)
    try:
        r = json.loads(p.stdout); txt = r.get("result", "")
        if not re.search(r"(【7|#+\s*7|\*\*7)", txt): raise ValueError("incomplete")
        (out / f"{t}.md").write_text(txt)
        (out / f"{t}.meta.json").write_text(json.dumps({"secs": round(time.time() - t0), "turns": r.get("num_turns"), "cost": r.get("total_cost_usd")}))
        return t, "ok"
    except Exception as e:
        (out / f"{t}.err").write_text(str(e) + "\n" + p.stdout[-1500:] + p.stderr[-500:]); return t, "err"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t, s in ex.map(one, json.load(open(tl))): print(t, s, flush=True)
