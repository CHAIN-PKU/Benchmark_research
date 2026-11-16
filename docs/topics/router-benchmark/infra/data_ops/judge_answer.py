#!/usr/bin/env python3
"""带答案对照：给判断者题面+标准解+测试，判断 DS 能否通过（对照'不给答案'）。"""
import json, pathlib, subprocess, datetime, concurrent.futures as cf, sys
DS=pathlib.Path("/home/ubuntu/swe-rebench-test/swe-rebench-07-2026")
W=pathlib.Path("/home/ubuntu/benchmark_router_paper/e3_exp")
out=W/"out/withanswer_sonnet"; out.mkdir(parents=True, exist_ok=True)
TASKS=json.load(open(W/"e3_tasks.json"))["tasks"]
model=sys.argv[1] if len(sys.argv)>1 else "claude-sonnet-5-5"
jobs=int(sys.argv[2]) if len(sys.argv)>2 else 3
PROMPT="""你是「动手前预测器」的判断环节。下面是任务题面、参考解（标准答案）和测试脚本，以及一个做题 AI 的说明。
请根据这些信息判断编程智能体 DeepSeek 能否通过该题隐藏测试，给出失败概率。
注意：真实派活时看不到标准答案和测试；这一组是「看答案」的对照上界。
只输出一行 JSON：{{"task":"{task}","p_fail":0~1}}
===== 题面 =====
{issue}
===== 参考解 =====
{sol}
===== 测试 =====
{test}
"""
def read(p, n):
    try: return p.read_text(errors="ignore")[:n]
    except Exception: return ""
def one(t):
    op=out/f"{t}.json"
    if op.exists(): return t,"skip"
    d=DS/t
    issue=read(d/"instruction.md",4000)
    sol=read(d/"solution/solve.sh",6000)
    test=read(d/"tests/test.sh",2500)
    prompt=PROMPT.format(task=t,issue=issue,sol=sol,test=test)
    env={"HOME":"/home/ubuntu","PATH":"/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"}
    for line in pathlib.Path("/home/ubuntu/.dsh/sonnet.env").read_text().splitlines():
        if "CLAUDE_CODE_OAUTH_TOKEN=" in line: env["CLAUDE_CODE_OAUTH_TOKEN"]=line.split("=",1)[1].strip().strip('"')
    try:
        p=subprocess.run(["/home/ubuntu/.local/bin/claude","-p",prompt,"--output-format","json","--model",model,
                          "--max-turns","2","--tools","","--setting-sources","","--strict-mcp-config"],
                         cwd="/tmp",env=env,capture_output=True,text=True,timeout=420)
        txt=json.loads(p.stdout).get("result","")
        dec=json.JSONDecoder(); obj=None
        for i in reversed([k for k,c in enumerate(txt) if c=="{"]):
            try: o,_=dec.raw_decode(txt,i)
            except Exception: continue
            if isinstance(o,dict) and "p_fail" in o: obj=o; break
        if obj is None: raise ValueError("no json")
        obj["task"]=t; obj["judged_at"]=datetime.datetime.now().strftime("%F %T")
        op.write_text(json.dumps(obj,ensure_ascii=False)); return t,"ok"
    except Exception as e:
        (out/f"{t}.err").write_text(str(e)[:300]); return t,"err"
with cf.ThreadPoolExecutor(jobs) as ex:
    for t,s in ex.map(one,TASKS): print(t,s,flush=True)
