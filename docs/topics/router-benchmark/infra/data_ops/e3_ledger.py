import json, pathlib, re, hashlib, datetime, csv
W=pathlib.Path("/home/ubuntu/benchmark_router_paper/e3_exp")
H=pathlib.Path("/home/ubuntu/swe-rebench-test/jobs")
TASKS=json.load(open(W/"e3_tasks.json"))["tasks"]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
# DS 开跑时间：job 目录名的 epoch
starts={}
for d in H.iterdir():
    m=re.match(r"srb-claude-code-(.*)-(\d+)-(\d+)$", d.name)
    if not m: continue
    task=m.group(1); ts=int(m.group(3))
    t=datetime.datetime.fromtimestamp(ts).strftime("%F %T")
    if task not in starts or t<starts[task]: starts[task]=t
rows=[]
for t in TASKS:
    pf=W/"prompts"/f"{t}.txt"
    if not pf.exists(): continue
    wt=datetime.datetime.fromtimestamp(pf.stat().st_mtime).strftime("%F %T")
    row={"task":t,"prompt_sha256":sha(pf)[:16],"written_at":wt,"ds_started_at":starts.get(t,""),
         "valid_before_start": (t not in starts) or (wt<starts[t])}
    for model in ("claude-haiku-5-5","claude-sonnet-5-5"):
        op=W/"out"/model/f"{t}.json"
        if op.exists():
            try: j=json.loads(op.read_text())
            except: j={}
            row[f"{model}_p_fail"]=j.get("p_fail"); row[f"{model}_judged_at"]=j.get("judged_at")
    rows.append(row)
out=W/"e3_ledger.json"
json.dump(rows, open(out,"w"), ensure_ascii=False, indent=1)
with open(W/"e3_write_times.csv","w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
nvalid=sum(1 for r in rows if r["valid_before_start"])
print("tasks",len(rows),"valid_before_DS_start",nvalid,"already_started",sum(1 for r in rows if r["ds_started_at"]))
hh=sum(1 for r in rows if r.get("claude-haiku-5-5_p_fail") is not None)
ss=sum(1 for r in rows if r.get("claude-sonnet-5-5_p_fail") is not None)
print("judged haiku",hh,"sonnet",ss)
PH=W/"prompts"
print("prompts_sha_all", hashlib.sha256("".join(sha(PH/f"{t}.txt") for t in TASKS if (PH/f"{t}.txt").exists()).encode()).hexdigest()[:16])
