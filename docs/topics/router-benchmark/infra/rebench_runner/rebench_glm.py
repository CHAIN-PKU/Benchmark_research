#!/usr/bin/env python3
"""SWE-rebench GLM 做题：cleared 题、oracle 自检复用已有结果则跳过、GLM 1 次；结果写 results_rebench_glm.jsonl。"""
import json, os, pathlib, subprocess, time
B = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval")
H = pathlib.Path("/home/ubuntu/swe-rebench-test")
HARBOR = "/home/ubuntu/harbor_env/bin/harbor"
CLEARED = B/"predictor_rebench_cleared.txt"
OUT = H/"results_rebench_glm.jsonl"
LOG = H/"rebench_glm.log"
BASE = "http://172.17.0.1/glmproxy"
def log(m):
    line = time.strftime("[%F %T] ")+str(m); open(LOG,"a").write(line+"\n"); print(line, flush=True)
def sh(c,t=2700): return subprocess.run(c,shell=True,capture_output=True,text=True,timeout=t)
def disk():
    r=sh("df -P / | awk 'NR==2{print $5}' | tr -d '%'")
    try: return int(r.stdout.strip())
    except: return 0
def done(t, kind, rep):
    if not OUT.exists(): return False
    for l in OUT.read_text().splitlines():
        try: r=json.loads(l)
        except: continue
        if r.get("task")==t and r.get("kind")==kind and r.get("rep")==rep: return True
    return False
def run(task, kind, rep):
    job=f"srbg-{kind}-{task[:16].replace('_','-')}-{rep}-{int(time.time())}"
    cmd=f"cd {H} && {HARBOR} run -p swe-rebench-07-2026/{task} -e docker -a claude-code -o jobs --job-name {job}"
    cmd+=(" -m z-ai/glm-5.3-flashx --ak base_url="+BASE+" --ak max_turns=500 --ak reasoning_effort=high"
          " --ak disable_web_search=true --ak disallowed_tools=WebFetch,WebSearch"
          " --ae ANTHROPIC_API_KEY=sk-local --ae ANTHROPIC_BASE_URL="+BASE+" --allow-agent-host 172.17.0.1")
    sh(cmd)
    rec={"task":task,"kind":kind,"rep":rep,"job":job,"model":"glm","at":time.strftime("%F %T")}
    rp=H/"jobs"/job/"result.json"
    if rp.exists():
        try:
            d=json.loads(rp.read_text()); st=d.get("stats") or {}
            for k,v in (st.get("evals") or {}).items():
                rec["metrics"]=v.get("metrics"); rec["exceptions"]=v.get("exception_stats")
        except Exception as e: rec["parse_error"]=str(e)[:200]
    open(OUT,"a").write(json.dumps(rec,ensure_ascii=False)+"\n")
    log(f"done {task} {kind}{rep} {rec.get('metrics')}")
    sh("sudo docker images --format '{{.ID}} {{.Repository}}' | grep -Ei 'swe-rebench|swerebench' | awk '{print $1}' | xargs -r sudo docker rmi -f >/dev/null 2>&1")
def main():
    wk=int(os.environ.get("RB_WK","0")); nw=int(os.environ.get("RB_NW","1"))
    while True:
        cleared=[l.strip() for l in CLEARED.read_text().splitlines() if l.strip()] if CLEARED.exists() else []
        todo=[t for t in cleared if not done(t,"claude-code",1)]
        todo=[x for i,x in enumerate(todo) if i%nw==wk]
        if not todo: time.sleep(600); continue
        for t in todo:
            while disk()>=88:
                sh("sudo docker image prune -f >/dev/null 2>&1; sudo docker builder prune -af >/dev/null 2>&1"); time.sleep(120)
            if not done(t,"claude-code",1):
                try: run(t,"claude-code",1)
                except Exception as e: log(f"ERR {t} {str(e)[:150]}")
if __name__=="__main__": main()
