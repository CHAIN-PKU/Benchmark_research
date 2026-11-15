import json, sys, os, random, csv
S=sys.argv[1]
fail=(set(os.listdir(S+"/rb_attr"))|set(os.listdir(S+"/rb_attr2")))-{"axios__axios-5316"}
def auc(s,l):
    p=[a for a,b in zip(s,l) if b]; n=[a for a,b in zip(s,l) if not b]
    return round(sum((x>z)+0.5*(x==z) for x in p for z in n)/len(p)/len(n),3)
def ci(s,l,B=3000):
    rng=random.Random(1); v=[]; idx=range(len(s))
    for _ in range(B):
        k=[rng.choice(idx) for _ in idx]; ll=[l[i] for i in k]
        if any(ll) and not all(ll): v.append(auc([s[i] for i in k],ll))
    v.sort(); return (v[int(.025*len(v))], v[int(.975*len(v))])
def jl(files):
    d={}
    for f in files:
        if not os.path.exists(f"{S}/{f}"): return None
        for l in open(f"{S}/{f}"):
            if l.strip(): r=json.loads(l); d[r["task"].replace(".md","")]=r
    return d
def cv(files):
    d={}
    for f in files:
        if not os.path.exists(f"{S}/{f}"): return None
        for r in csv.DictReader(open(f"{S}/{f}")): d[r["task"].replace(".md","")]=r
    return d
cells={"Opus+checklist(N)":(jl([f"dm_N_part{i}.jsonl" for i in range(1,5)]),"p_fail"),
 "Sonnet+checklist":(jl(["dm_SC_half1.jsonl","dm_SC_half2.jsonl"]),"p_fail"),
 "Opus+generic":(cv(["og_half1.csv","og_half2.csv"]),"p_hard"),
 "Sonnet+generic":(cv(["sg_half1.csv","sg_half2.csv"]),"p_hard"),
 "Sonnet+generic(issue-only,void)":(cv(["sg_all.csv"]),"p_hard")}
for k,(D,f) in cells.items():
    if D is None: print(k,"pending"); continue
    ts=sorted(D); y=[t in fail for t in ts]; s=[float(D[t][f]) for t in ts]
    print(k,f,"n=",len(ts),"fails=",sum(y),auc(s,y),ci(s,y))
