import json, sys, os, random, glob
A, OUT = sys.argv[1], sys.argv[2]   # attr 目录（标签）、out 目录
fail=(set(os.listdir(A+"/rb_attr"))|set(os.listdir(A+"/rb_attr2")))-{"axios__axios-5316"}
tasks=json.load(open(A+"/../predictor_xmodel/tasks.json"))
def auc(s,l):
    p=[a for a,b in zip(s,l) if b]; n=[a for a,b in zip(s,l) if not b]
    return sum((x>z)+0.5*(x==z) for x in p for z in n)/len(p)/len(n)
def ci(s,l,B=3000):
    rng=random.Random(1); v=[]; idx=range(len(s))
    for _ in range(B):
        k=[rng.choice(idx) for _ in idx]; ll=[l[i] for i in k]
        if any(ll) and not all(ll): v.append(auc([s[i] for i in k],ll))
    v.sort(); return round(v[int(.025*len(v))],3), round(v[int(.975*len(v))],3)
for d in sorted(glob.glob(OUT+"/*/")):
    D={}
    for f in glob.glob(d+"*.json"):
        r=json.load(open(f)); D[r["task"]]=r
    ts=[t for t in tasks if t in D]; y=[t in fail for t in ts]
    if len(ts)<20 or not any(y): print(os.path.basename(d[:-1]),"n=",len(ts),"too few"); continue
    for fld in ("p_fail","risk_hidden"):
        s=[float(D[t].get(fld) or 0) for t in ts]
        print(os.path.basename(d[:-1]), fld, "n=",len(ts),"fails=",sum(y), round(auc(s,y),3), ci(s,y))
