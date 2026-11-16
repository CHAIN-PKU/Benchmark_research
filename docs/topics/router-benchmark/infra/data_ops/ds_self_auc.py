import json,pathlib
pred=json.load(open("/home/ubuntu/benchmark_router_paper/claude_eval/predictor_prosp/out/ds_gen_agg.json"))
R=pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot/runs")
lab={}
for t in pred:
    d=R/t; vals=[]
    for r in (1,2):
        p=d/f"dsh_r{r}"/"record.json"
        if p.exists():
            try: x=json.loads(p.read_text())
            except: continue
            if x.get("hint"): continue
            vals.append(x.get("resolved"))
    vals=[v for v in vals if v is not None]
    if vals: lab[t]=1 if any(vals) else 0
def auc(ps):
    pos=[p for p,y in ps if y==1]; neg=[p for p,y in ps if y==0]
    if not pos or not neg: return None,len(ps)
    s=sum(1 if p>n else (0.5 if p==n else 0) for p in pos for n in neg)
    return round(s/(len(pos)*len(neg)),3),len(ps)
tasks=[t for t in pred if t in lab]
print("A p_fail vs fail-label",auc([(pred[t]["mean"],1-lab[t]) for t in tasks]))
print("B p_pass vs pass-label",auc([(1-pred[t]["mean"],lab[t]) for t in tasks]))
print("C p_fail vs pass-label",auc([(pred[t]["mean"],lab[t]) for t in tasks]))
print("D p_pass vs fail-label",auc([(1-pred[t]["mean"],1-lab[t]) for t in tasks]))
