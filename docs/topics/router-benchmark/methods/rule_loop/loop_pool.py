import json,glob,os,numpy as np
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
R='dossier'; D=json.load(open('tagging/tag_data.json')); subs=[json.load(open(f)) for f in glob.glob('pubhist/ml_*.json')]
E={tag:{} for tag in ('final','seed')}; C={}
for f in (0,1):
    for tag in E:
        e=json.load(open(f'{R}/out_loop/fold{f}/eval_{tag}.json')); E[tag].update(e['p']); 
    ev=json.load(open(f'{R}/out_loop/fold{f}/eval_final.json')); 
    for t in ev['p']: C[t]=ev['brier_const']  # 占位
def ld(d): return {json.load(open(x))['task']:float(json.load(open(x))['p_fail']) for x in glob.glob(f'{R}/{d}/*.json')}
H=ld('out_judge_full/dos_haiku'); S=ld('out_judge_full/dos_sonnet')
ts=sorted(t for t in E['final'] if t in H and t in S and all(t in s for s in subs)); y=np.array([int(D[t]['passes']<D[t]['runs']) for t in ts])
FO=json.load(open('refjudge/repo_fold.json')); fo=np.array([FO[D[t]['repo']] for t in ts]); const=np.array([y[fo!=f].mean() if False else 0 for f in fo],float)
for f in (0,1): const[fo==f]=np.mean([int(D[t]['passes']<D[t]['runs']) for t in D if t in H and D[t]['repo'] in FO and FO[D[t]['repo']]!=f])
diff=np.array([np.mean([0 if s[t]['resolved'] else 1 for s in subs]) for t in ts])
A={'规则闭环（最终）':np.array([E['final'][t] for t in ts]),'规则（起始 8 条，未迭代）':np.array([E['seed'][t] for t in ts]),'档案+Haiku（无历史）':np.array([H[t] for t in ts]),'档案+Sonnet（无历史）':np.array([S[t] for t in ts])}
rng=np.random.default_rng(0); B=[rng.integers(0,len(ts),len(ts)) for _ in range(2000)]
print(f'n={len(ts)} DS挂{y.sum()}  常数 Brier {np.mean((const-y)**2):.4f}')
for k,p in A.items():
    au=np.mean([roc_auc_score([0 if s[t]['resolved'] else 1 for t in ts],p) for s in subs])
    print(f"{k:22s} DS AUC {roc_auc_score(y,p):.3f} 区间{np.round(np.percentile([roc_auc_score(y[i],p[i]) for i in B if len(set(y[i]))==2],[2.5,97.5]),2)} | 14家AUC {au:.3f} 相关 {spearmanr(p,diff)[0]:+.3f} | Brier {np.mean((p-y)**2):.4f}")
for k in ('规则闭环（最终）','规则（起始 8 条，未迭代）'):
    d=[roc_auc_score(y[i],A[k][i])-roc_auc_score(y[i],A['档案+Haiku（无历史）'][i]) for i in B if len(set(y[i]))==2]; b=[np.mean((A[k][i]-y[i])**2)-np.mean((const[i]-y[i])**2) for i in B]
    print(f"{k} − 档案+Haiku DS AUC 区间 {np.round(np.percentile(d,[2.5,97.5]),3)} | Brier − 常数 区间 {np.round(np.percentile(b,[2.5,97.5]),4)}")
for f in (0,1):
    m=fo==f; print('留出折 fold',f,'n',m.sum(),'规则闭环 AUC %.3f'%roc_auc_score(y[m],A['规则闭环（最终）'][m]),'起始 %.3f'%roc_auc_score(y[m],A['规则（起始 8 条，未迭代）'][m]),'Haiku %.3f'%roc_auc_score(y[m],A['档案+Haiku（无历史）'][m]),'Sonnet %.3f'%roc_auc_score(y[m],A['档案+Sonnet（无历史）'][m]))
