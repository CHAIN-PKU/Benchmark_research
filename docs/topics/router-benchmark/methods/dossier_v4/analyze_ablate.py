import json,glob,os,sys,numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
S=sys.argv[1]; D=json.load(open(f'{S}/tagging/tag_data.json')); subs=[json.load(open(f)) for f in glob.glob(f'{S}/pubhist/ml_*.json')]
def arm(d):
    P={}
    for f in glob.glob(d+'/*.json'):
        r=json.load(open(f))
        if 'p_fail' in r: P[r['task']]=float(r['p_fail'])
    return P
NAMES={1:'题面要点',2:'相关代码',3:'并列与牵连',4:'现有测试与约定',5:'边界与隐含要求',6:'改动规模',7:'难点一句话'}
A={'完整档案':arm(f'{S}/dossier/out_judge_full/dos_haiku')}
for k in range(1,8): A[f'删第{k}节 {NAMES[k]}']=arm(f'{S}/dossier/out_ablate/drop{k}_haiku')
ts=[t for t in D if all(t in s for s in subs) and all(t in a for a in A.values())]
diff=np.array([np.mean([0 if s[t]['resolved'] else 1 for s in subs]) for t in ts])
rng=np.random.default_rng(0); idx=[rng.integers(0,len(ts),len(ts)) for _ in range(2000)]
base=np.array([A['完整档案'][t] for t in ts]); r0=spearmanr(base,diff)[0]
print('n',len(ts),'完整档案相关',round(r0,3))
for k,a in A.items():
    if k=='完整档案': continue
    p=np.array([a[t] for t in ts]); r=spearmanr(p,diff)[0]
    d=[spearmanr(p[i],diff[i])[0]-spearmanr(base[i],diff[i])[0] for i in idx]
    print(f'{k:16s} 相关 {r:.3f}  变化 {r-r0:+.3f} [{np.percentile(d,2.5):+.3f},{np.percentile(d,97.5):+.3f}]  均值 {p.mean():.2f}')
