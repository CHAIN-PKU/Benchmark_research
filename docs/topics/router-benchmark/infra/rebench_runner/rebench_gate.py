#!/usr/bin/env python3
"""SWE-rebench 闸门跑：只跑 predictor_rebench_cleared.txt 放行的题；oracle 自检 + DS 2 次。"""
import json, os, pathlib, subprocess, time
B = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval")
H = pathlib.Path("/home/ubuntu/swe-rebench-test")
HARBOR = "/home/ubuntu/harbor_env/bin/harbor"
CLEARED = B/"predictor_rebench_cleared.txt"
OUT = H/"results_rebench.jsonl"
LOG = H/"rebench_gate.log"
BASE = "http://172.17.0.1/dshproxy"
def log(m):
    line = time.strftime("[%F %T] ")+str(m); open(LOG,"a").write(line+"\n"); print(line, flush=True)
def sh(c, t=7200): return subprocess.run(c, shell=True, capture_output=True, text=True, timeout=t)
def disk():
    r=sh("df -P / | awk 'NR==2{print $5}' | tr -d '%'")
    try: return int(r.stdout.strip())
    except: return 0
def guard():
    while disk()>=88:
        log(f"disk {disk()}% prune"); sh("sudo docker image prune -f >/dev/null 2>&1; sudo docker builder prune -af >/dev/null 2>&1")
        if disk()<90: return
        time.sleep(120)
def done(t,kind,rep):
    if not OUT.exists(): return False
    for l in OUT.read_text().splitlines():
        try: r=json.loads(l)
        except: continue
        if r.get("task")==t and r.get("kind")==kind and r.get("rep")==rep: return True
    return False
def run(task,kind,rep):
    job=f"srb-{kind}-{task[:18].replace('_','-')}-{rep}-{int(time.time())}"
    cmd=f"cd {H} && {HARBOR} run -p swe-rebench-07-2026/{task} -e docker -a {kind} -o jobs --job-name {job}"
    if kind=="claude-code":
        cmd+=(" -m deepseek/deepseek-v4.1-flash --ak base_url="+BASE+
              " --ak max_turns=500 --ak reasoning_effort=xhigh --ak disable_web_search=true"
              " --ak disallowed_tools=WebFetch,WebSearch --ae ANTHROPIC_API_KEY=sk-local"
              " --ae ANTHROPIC_BASE_URL="+BASE+" --allow-agent-host 172.17.0.1")
    sh(cmd)
    rec={"task":task,"kind":kind,"rep":rep,"job":job,"at":time.strftime("%F %T")}
    rp=H/"jobs"/job/"result.json"
    if rp.exists():
        try:
            d=json.loads(rp.read_text()); st=d.get("stats") or {}
            for k,v in (st.get("evals") or {}).items():
                rec["metrics"]=v.get("metrics"); rec["reward_stats"]=v.get("reward_stats"); rec["exceptions"]=v.get("exception_stats")
            rec["started_at"]=d.get("started_at"); rec["finished_at"]=d.get("finished_at")
        except Exception as e: rec["parse_error"]=str(e)[:200]
    open(OUT,"a").write(json.dumps(rec,ensure_ascii=False)+"\n")
    log(f"done {task} {kind} rep{rep} metrics={rec.get('metrics')}")
    # 清镜像
    sh("sudo docker images --format '{{.ID}} {{.Repository}}' | grep -Ei 'swe-rebench|swerebench' | awk '{print $1}' | xargs -r sudo docker rmi -f >/dev/null 2>&1")
def main():
    wk = int(os.environ.get("RB_WK", "0")); nw = int(os.environ.get("RB_NW", "1"))
    while True:
        cleared=[]
        if CLEARED.exists():
            cleared=[l.strip() for l in CLEARED.read_text().splitlines() if l.strip()]
        todo=[t for t in cleared if not (done(t,"oracle",0) and done(t,"claude-code",1) and done(t,"claude-code",2))]
        todo = [x for i, x in enumerate(todo) if i % nw == wk]
        if not todo:
            time.sleep(300); continue
        for t in todo:
            guard()
            if not done(t,"oracle",0): run(t,"oracle",0)
            for rep in (1,2):
                if done(t,"claude-code",rep): continue
                guard(); run(t,"claude-code",rep)
            log(f"cleanup {t}")
if __name__=="__main__": main()
