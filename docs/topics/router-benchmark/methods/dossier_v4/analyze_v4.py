import json,glob,os,sys,numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
S=sys.argv[1]; D=json.load(open(f'{S}/tagging/tag_data.json')); T=json.load(open(f'{S}/dossier/targets30.json'))
subs=[json.load(open(f)) for f in glob.glob(f'{S}/pubhist/ml_*.json')]
def arm(d): 
    P={}
    for f in glob.glob(d+'/*.json'):
        r=json.load(open(f))
        if 'p_fail' in r: P[r.get('task',os.path.basename(f)[:-5])]=float(r['p_fail'])
    return P
A={'读仓库直接判(sonnet_tags)':arm(f'{S}/train_tags/out/sonnet_tags'),
   '3条线索 Sonnet':arm(f'{S}/refjudge/out_judge/none_sonnet'),'3条线索 Haiku':arm(f'{S}/refjudge/out_judge/none_haiku'),
   '档案 Sonnet':arm(f'{S}/dossier/out_judge/dos_sonnet'),'档案 Haiku':arm(f'{S}/dossier/out_judge/dos_haiku'),
   '档案+案例 Sonnet':arm(f'{S}/dossier/out_judge/case_sonnet'),'档案+案例 Haiku':arm(f'{S}/dossier/out_judge/case_haiku')}
ts=[t for t in T if all(t in a for a in A.values())]
diff=np.array([np.mean([0 if s[t]['resolved'] else 1 for s in subs]) for t in ts]); y=np.array([int(D[t]['passes']<D[t]['runs']) for t in ts])
print('n',len(ts),'DS fails',y.sum())
for k,a in A.items():
    p=np.array([a[t] for t in ts]); au=np.mean([roc_auc_score([0 if s[t]['resolved'] else 1 for t in ts],p) for s in subs])
    print(f'{k:24s} 公开难度相关 {spearmanr(p,diff)[0]:+.3f}  14家平均AUC {au:.3f}  DS AUC {roc_auc_score(y,p):.3f}')
