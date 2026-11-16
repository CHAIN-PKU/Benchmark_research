import csv, json, pathlib
B=pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/predictor_xmodel/judge_patch")
lab={r["task"]:int(r["label"]) for r in csv.DictReader(open(B/"labels.csv"))}
def auc(pairs):
    pos=[p for p,y in pairs if y==1]; neg=[p for p,y in pairs if y==0]
    if not pos or not neg: return None
    s=sum(1 if p>n else (0.5 if p==n else 0) for p in pos for n in neg)
    return round(s/(len(pos)*len(neg)),3)
rows=[]
for d in sorted((B/"out").iterdir()):
    if not d.is_dir(): continue
    pairs=[]; imputed=0
    for p in d.glob("*.json"):
        j=json.loads(p.read_text()); t=j.get("task") or p.stem
        if t not in lab: continue
        if j.get("imputed"): imputed+=1; continue
        pp=j.get("p_pass")
        if pp is None and j.get("p_fail") is not None: pp=1-float(j["p_fail"])
        if pp is not None: pairs.append((float(pp), lab[t]))
    rows.append({"judge":d.name,"auc":auc(pairs),"n":len(pairs),"imputed":imputed,"base_rate":round(sum(lab.values())/len(lab),3)})
out=pathlib.Path("/home/ubuntu/benchmark_router_paper/judge_auc_final_20261116.csv")
w=csv.DictWriter(open(out,"w",newline=""),fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(out)
for r in rows: print(r)
