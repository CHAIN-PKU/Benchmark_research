#!/usr/bin/env python3
"""E3 判断：读 prompts/<task>.txt，调 claude CLI，输出 out/<model>/<task>.json + 逐题时间。"""
import json, pathlib, subprocess, sys, concurrent.futures as cf, datetime
W=pathlib.Path("/home/ubuntu/benchmark_router_paper/e3_exp")
model=sys.argv[1]; jobs=int(sys.argv[2]) if len(sys.argv)>2 else 2
out=W/"out"/model; out.mkdir(parents=True, exist_ok=True)
def extract(text):
    dec=json.JSONDecoder()
    for i in reversed([k for k,c in enumerate(text) if c=="{"]):
        try: o,_=dec.raw_decode(text,i)
        except Exception: continue
        if isinstance(o,dict) and "p_fail" in o: return o
    raise ValueError("no json")
def one(t):
    op=out/f"{t}.json"
    if op.exists(): return t,"skip"
    prompt=(W/"prompts"/f"{t}.txt").read_text()
    env={"HOME":"/home/ubuntu","PATH":"/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin"}
    # 从 sonnet.env 读 token
    tok=None
    for line in pathlib.Path("/home/ubuntu/.dsh/sonnet.env").read_text().splitlines():
        if "CLAUDE_CODE_OAUTH_TOKEN=" in line: tok=line.split("=",1)[1].strip().strip('"')
    if tok: env["CLAUDE_CODE_OAUTH_TOKEN"]=tok
    try:
        p=subprocess.run(["/home/ubuntu/.local/bin/claude","-p",prompt,"--output-format","json","--model",model,
                          "--max-turns","2","--tools","","--setting-sources","","--strict-mcp-config",
                          "--disable-slash-commands"], cwd="/tmp", env=env, capture_output=True, text=True, timeout=420)
        d=json.loads(p.stdout); txt=d.get("result","") or ""
        o=extract(txt); o["task"]=t; o["judged_at"]=datetime.datetime.now().strftime("%F %T")
        o["cost"]=d.get("total_cost_usd")
        op.write_text(json.dumps(o,ensure_ascii=False))
        return t,"ok"
    except Exception as e:
        (out/f"{t}.err").write_text(str(e)[:300]); return t,"err"
tasks=[p.stem for p in sorted((W/"prompts").glob("*.txt"))]
with cf.ThreadPoolExecutor(jobs) as ex:
    for t,s in ex.map(one,tasks): print(t,s,flush=True)
