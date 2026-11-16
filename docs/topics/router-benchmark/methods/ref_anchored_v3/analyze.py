import json,glob,sys,numpy as np
from sklearn.metrics import roc_auc_score
S=sys.argv[1]; D=json.load(open(f'{S}/tagging/tag_data.json'))
def arm(a): return {json.load(open(f))['task']:float(json.load(open(f))['p_fail']) for f in glob.glob(f'{S}/refjudge/out_judge/{a}/*.json')}
rng=np.random.default_rng(0)
for m in ['sonnet','haiku']:
    A={k:arm(f'{k}_{m}') for k in ['none','rand','sim']}
    ts=[t for t in D if all(t in a for a in A.values())]
    y=np.array([int(D[t]['passes']<D[t]['runs']) for t in ts]); ys=np.array([int(D[t]['passes']==0) for t in ts])
    P={k:np.array([a[t] for t in ts]) for k,a in A.items()}
    print(m,'n',len(ts),'fails',y.sum(),' '.join(f'{k}:{roc_auc_score(y,v):.3f}(严格{roc_auc_score(ys,v):.3f},均值{v.mean():.2f})' for k,v in P.items()))
    for a,b in [('sim','none'),('rand','none'),('sim','rand')]:
        d=[]
        for _ in range(2000):
            i=rng.integers(0,len(ts),len(ts))
            if y[i].min()==y[i].max(): continue
            d.append(roc_auc_score(y[i],P[a][i])-roc_auc_score(y[i],P[b][i]))
        print(f'   {a}-{b}: {np.mean(d):+.3f} [{np.percentile(d,2.5):+.3f},{np.percentile(d,97.5):+.3f}]')
