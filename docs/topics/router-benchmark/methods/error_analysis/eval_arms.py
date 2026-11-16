import json,glob,os,sys,numpy as np
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
R=os.path.dirname(os.path.abspath(__file__)); S=os.path.dirname(R)
D=json.load(open(f"{S}/tagging/tag_data.json")); subs=[json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
ld=lambda d:{json.load(open(f))['task']:float(json.load(open(f))['p_fail']) for f in glob.glob(f"{R}/{d}/*.json")}
pairs=[a.split('=') for a in sys.argv[1:]]  # 名称=目录 基线名称=目录 ...
arms={n:ld(d) for n,d in pairs}
ts=sorted(set.intersection(*[set(v) for v in arms.values()])&set(D)); y=np.array([int(D[t]['passes']<D[t]['runs']) for t in ts])
pub=[i for i,t in enumerate(ts) if all(t in s for s in subs)]; diff=np.array([np.mean([0 if s[ts[i]]['resolved'] else 1 for s in subs]) for i in pub])
rng=np.random.default_rng(0); B=[rng.integers(0,len(ts),len(ts)) for _ in range(2000)]; au=lambda p,i: roc_auc_score(y[i],p[i]) if len(set(y[i]))==2 else np.nan
print('n',len(ts),'DS挂',y.sum())
P={n:np.array([arms[n][t] for t in ts]) for n in arms}
for n,p in P.items(): print(f"{n:20s} DS AUC {roc_auc_score(y,p):.3f} [{np.nanpercentile([au(p,i) for i in B],2.5):.2f},{np.nanpercentile([au(p,i) for i in B],97.5):.2f}] | 与14家难度相关 {spearmanr(p[pub],diff)[0]:+.3f} | 平均p {p.mean():.2f}")
names=list(P)
for a in names[1:]:
    b=names[0]; d=[au(P[a],i)-au(P[b],i) for i in B]; print(f"{a} − {b}: DS AUC 区间 {np.round(np.nanpercentile(d,[2.5,97.5]),3)}")
