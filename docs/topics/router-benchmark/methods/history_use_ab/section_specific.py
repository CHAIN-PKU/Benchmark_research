# 检查：哪一节对 DS 的预测超出「公开难度」本身（DS 特有信号）。控制公开难度后，看各节对 DS 成败的偏 AUC（按公开难度分 4 层内算 AUC 再平均）
import json,glob,os,numpy as np
from sklearn.metrics import roc_auc_score
S=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=json.load(open(f"{S}/tagging/tag_data.json")); subs=[json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
R={json.load(open(f))["task"]:json.load(open(f)) for f in glob.glob(f"{S}/dossier/out_secrisk/haiku/*.json")}
ts=sorted(t for t in R if all(t in s for s in subs))
y=np.array([int(D[t]["passes"]<D[t]["runs"]) for t in ts]); diff=np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts])
q=np.digitize(diff,np.quantile(diff,[.25,.5,.75]))
def strat(x):
    a=[];w=[]
    for k in range(4):
        m=q==k
        if len(set(y[m]))==2: a.append(roc_auc_score(y[m],x[m])); w.append(m.sum())
    return np.average(a,weights=w)
for k in ["r1","r2","r3","r4","r5","r6","r7","p_fail"]:
    x=np.array([float(R[t][k]) for t in ts])
    au=np.mean([roc_auc_score([0 if s[t]["resolved"] else 1 for t in ts],x) for s in subs])
    print(k,"控制公开难度后 DS 分层AUC %.3f"%strat(x),"  14家平均AUC %.3f"%au)
print("公开难度本身 DS AUC %.3f"%roc_auc_score(y,diff))
