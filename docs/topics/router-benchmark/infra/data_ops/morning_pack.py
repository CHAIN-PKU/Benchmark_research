import csv, hashlib, json, pathlib
B = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval")
OUT = pathlib.Path("/home/ubuntu/benchmark_router_paper/morning_pack_20261116"); OUT.mkdir(exist_ok=True)

def recs(taskdir):
    m={}
    for r in sorted(taskdir.glob("dsh_r*/record.json")):
        try: d=json.loads(r.read_text())
        except: continue
        try: rep=int(d.get("rep") or r.parent.name.split("_r")[-1])
        except: rep=0
        m[rep]=d
    return m

def label(m):
    # 取前两个非 hint 运行的多数/后者；无则 None
    rs=[(k,v) for k,v in sorted(m.items()) if not v.get("hint")]
    if not rs: return None
    vals=[v.get("resolved") for k,v in rs[:2] if v.get("resolved") is not None]
    if not vals: return None
    return 1 if any(vals) else 0

# 1) 测试集主表
cl=[l.strip() for l in (B/"predictor_cleared.txt").read_text().splitlines() if l.strip()]
rows=[]
for t in cl:
    m=recs(B/"ds_pilot/runs"/t)
    env=[k for k,v in m.items() if v.get("env_error")]
    rows.append({"task":t,"runs":len(m),"reps":",".join(str(k) for k in sorted(m)),
                 "label":label(m),"env_error":len(env),
                 "hint_runs":sum(1 for v in m.values() if v.get("hint"))})
csv.writer(open(OUT/"test123_status.csv","w",newline="")).writerows([list(rows[0])]+[[r[k] for k in rows[0]] for r in rows])

# 2) 干预 prepost
sel=json.loads((B/"ds_pilot/selection.json").read_text()); tasks=sel["fail"]+sel["pass"]
irows=[]
for t in tasks:
    m=recs(B/"ds_pilot/runs"/t)
    base=[v.get("resolved") for k,v in m.items() if not v.get("hint") and v.get("resolved") is not None]
    hint=[v.get("resolved") for k,v in m.items() if v.get("hint") and v.get("resolved") is not None]
    irows.append({"task":t,"base_n":len(base),"base_pass":sum(1 for x in base if x),
                  "hint_n":len(hint),"hint_pass":sum(1 for x in hint if x)})
csv.writer(open(OUT/"intervention_prepost.csv","w",newline="")).writerows([list(irows[0])]+[[r[k] for k in irows[0]] for r in irows])

# 3) 判卷 AUC（tags in out_judge + judge_patch/out models）
def auc(pairs):
    pts=[(p,1 if y else 0) for p,y in pairs if p is not None and y is not None]
    if len(pts)<10: return None, len(pts)
    pos=[p for p,y in pts if y==1]; neg=[p for p,y in pts if y==0]
    if not pos or not neg: return None, len(pts)
    s=0
    for p in pos:
        for n in neg:
            s += 1 if p>n else (0.5 if p==n else 0)
    return round(s/(len(pos)*len(neg)),3), len(pts)

labels={}
for t in cl:
    m=recs(B/"ds_pilot/runs"/t)
    labels[t]=label(m)
for extra in (B/"ds_pilot/runs").glob("*"):
    if extra.name not in labels:
        labels[extra.name]=label(recs(extra))
arows=[]
def scan(name, root, key):
    d=root/name
    if not d.exists(): return
    pairs=[]
    for p in sorted(d.glob("*.json")):
        try: j=json.loads(p.read_text())
        except: continue
        t=j.get("task") or p.stem
        if t in labels and labels[t] is not None:
            pv=j.get(key)
            pairs.append((pv, labels[t]))
    a,n=auc(pairs)
    arows.append({"predictor":name,"auc":a,"n":n})
for t in ("sonnetEv_dsJudge","R_sonnetEv_ds","R_sonnetEv_glm","RUB_sonnetEv_ds","RUB_sonnetEv_glm","FS_sonnetEv_ds","FS_sonnetEv_glm","rule_ds"):
    scan(t, B/"predictor_xmodel/out_judge", "p_fail")
if arows:
    csv.writer(open(OUT/"judge_auc.csv","w",newline="")).writerows([list(arows[0])]+[[r[k] for k in arows[0]] for r in arows])

# 4) 冻结台账
lrows=[]
for d in sorted((B/"predictor_prosp").glob("out/*")):
    files=sorted(d.glob("*.json")); h=hashlib.sha256()
    for p in files: h.update(p.name.encode()); h.update(p.read_bytes())
    lrows.append({"dir":str(d.relative_to(B)),"n":len(files),"sha256":h.hexdigest()[:16]})
if lrows:
    csv.writer(open(OUT/"frozen_ledger.csv","w",newline="")).writerows([list(lrows[0])]+[[r[k] for k in lrows[0]] for r in lrows])
print("pack files:", [p.name for p in OUT.iterdir()])
for f in OUT.iterdir(): print(f.name, sum(1 for _ in open(f))-1, "rows")
