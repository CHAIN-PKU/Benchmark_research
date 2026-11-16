import json,glob,os,sys,numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
S=sys.argv[1]; K=[f"V{i:02d}" for i in range(1,14)]
D=json.load(open(f'{S}/tagging/tag_data.json')); fold=json.load(open(f'{S}/feat2/repo_fold.json'))
def tags(split): return {json.load(open(f))['task']:np.array([json.load(open(f))[k] for k in K]) for f in glob.glob(f'{S}/feat2/out_tag/{split}/*.json')}
TO,TP=tags('old'),tags('prosp')
PO={json.load(open(f))['task']:float(json.load(open(f))['p_fail']) for f in glob.glob(f'{S}/train_tags/out/sonnet_tags/*.json')}
PP={json.load(open(f))['task']:float(json.load(open(f))['p_fail']) for f in glob.glob(f'{S}/prosp/out/sonnet_tags/*.json')}
ts=[t for t in D if t in TO and t in PO]; X=np.array([TO[t] for t in ts]); y=np.array([int(D[t]['passes']<D[t]['runs']) for t in ts]); p=np.array([PO[t] for t in ts]); f=np.array([fold[D[t]['repo']] for t in ts])
print('old n',len(ts),'fails',y.sum()); print('prevalence',' '.join(f'{k}:{v:.2f}' for k,v in zip(K,X.mean(0))))
print('单条（挂率 有/无）:',' '.join(f'{k}:{y[X[:,i]==1].mean():.2f}/{y[X[:,i]==0].mean():.2f}' for i,k in enumerate(K) if X[:,i].sum()>0))
oof=np.zeros(len(ts)); oofc=np.zeros(len(ts))
for k in (0,1):
    tr,te=f!=k,f==k
    m=LogisticRegression(C=0.5,max_iter=3000).fit(X[tr],y[tr]); oof[te]=m.predict_proba(X[te])[:,1]
    Z=np.c_[X,np.log(p/(1-p+1e-9)+1e-9)]; mc=LogisticRegression(C=0.5,max_iter=3000).fit(Z[tr],y[tr]); oofc[te]=mc.predict_proba(Z[te])[:,1]
print('内部（仓库两折）AUC：特征 %.3f | Sonnet p_fail %.3f | 合并 %.3f'%(roc_auc_score(y,oof),roc_auc_score(y,p),roc_auc_score(y,oofc)))
# external
m=LogisticRegression(C=0.5,max_iter=3000).fit(X,y); w=dict(zip(K,m.coef_[0].round(2))); print('全量权重',w)
subs={os.path.basename(x)[3:-5].split('_')[-1]:json.load(open(x)) for x in glob.glob(f'{S}/pubhist/ml_*.json')}
tp=[t for t in TP if t in PP and all(t in s for s in subs.values())]
XP=np.array([TP[t] for t in tp]); sc=m.predict_proba(XP)[:,1]; pp=np.array([PP[t] for t in tp])
Z=np.c_[X,np.log(p/(1-p+1e-9)+1e-9)]; mc=LogisticRegression(C=0.5,max_iter=3000).fit(Z,y); scc=mc.predict_proba(np.c_[XP,np.log(pp/(1-pp+1e-9)+1e-9)])[:,1]
a1=[];a2=[];a3=[]
for k,s in sorted(subs.items()):
    yy=np.array([0 if s[t]['resolved'] else 1 for t in tp]); a1.append(roc_auc_score(yy,sc)); a2.append(roc_auc_score(yy,pp)); a3.append(roc_auc_score(yy,scc))
print('外部 前瞻 %d 道 × 14 家平均 AUC：特征 %.3f | Sonnet p_fail %.3f | 合并 %.3f'%(len(tp),np.mean(a1),np.mean(a2),np.mean(a3)))
print('  各家 特征/Sonnet/合并:',' '.join(f'{k}:{x:.2f}/{y_:.2f}/{z:.2f}' for k,x,y_,z in zip(sorted(subs),a1,a2,a3)))
