import json,glob,os,sys,numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from scipy.stats import spearmanr
S=sys.argv[1]
sp=json.load(open(f'{S}/cues/split.json')); K=[f"C{i:02d}" for i in range(1,13)]
X={}
for f in glob.glob(f'{S}/cues/out_tag/haiku/*.json'):
    r=json.load(open(f)); X[r['task']]=np.array([r[k] for k in K])
subs={os.path.basename(f)[3:-5].split('_')[-1]:json.load(open(f)) for f in glob.glob(f'{S}/pubhist/ml_*.json')}
A=sorted(subs)
def YY(ts,a):
    ts=[t for t in ts if t in subs[a]]; return ts,np.array([0 if subs[a][t]['resolved'] else 1 for t in ts])
D,T=sp['derive'],sp['test']
def diff(ts): return np.array([np.mean([0 if subs[a][t]['resolved'] else 1 for a in A if t in subs[a]]) for t in ts])
XD=np.array([X[t] for t in D]); XT=np.array([X[t] for t in T]); dD,dT=diff(D),diff(T)
print('prevalence(derive)',' '.join(f'{k}:{v:.2f}' for k,v in zip(K,XD.mean(0))))
print('单条特征（总结集，14 家平均挂率）:')
for i,k in enumerate(K):
    m=XD[:,i]==1; print(f'  {k} n={m.sum():3d} 有 {dD[m].mean():.2f} 无 {dD[~m].mean():.2f}')
rows=[];ys=[]
for j,a in enumerate(A):
    ts,y=YY(D,a); oh=np.zeros(len(A)); oh[j]=1
    rows+= [np.r_[X[t],oh] for t in ts]; ys+=list(y)
m=LogisticRegression(C=0.3,max_iter=3000).fit(np.array(rows),np.array(ys)); w=m.coef_[0][:12]
print('合并权重',' '.join(f'{k}:{v:+.2f}' for k,v in zip(K,w)))
sT=XT@w
print('检验集 114：分数 vs 14家公开难度 秩相关 %.3f（只数特征个数 %.3f；总结集内 %.3f）'%(spearmanr(sT,dT)[0],spearmanr(XT.sum(1),dT)[0],spearmanr(XD@w,dD)[0]))
au=[];aus=[]
for a in A:
    ts,y=YY(T,a); idx=[T.index(t) for t in ts]
    au.append(roc_auc_score(y,sT[idx]))
    tsd,yd=YY(D,a); ma=LogisticRegression(C=0.3,max_iter=3000).fit(np.array([X[t] for t in tsd]),yd)
    aus.append(roc_auc_score(y,ma.predict_proba(XT[idx])[:,1]))
    print(f'  {a:18s} 合并 {au[-1]:.2f}  单家 {aus[-1]:.2f}')
print('检验集逐家 AUC：合并 %.3f（%.2f-%.2f）；单家模型 %.3f'%(np.mean(au),min(au),max(au),np.mean(aus)))
json.dump({'weights':dict(zip(K,w.tolist())),'C':0.3},open(f'{S}/cues/pooled_weights_v1.json','w'))
