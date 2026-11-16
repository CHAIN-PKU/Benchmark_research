# 第 4 章 Benchmark：同 84 道旧题、同快照、同清单，只换预测者模型
import json,glob,os,numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
S=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=json.load(open(f"{S}/tagging/tag_data.json")); subs=[json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
def load(d):
    P={}
    for f in glob.glob(d+"/*.json"):
        try: r=json.load(open(f)); P[r.get("task",os.path.basename(f)[:-5])]=float(r["p_fail"])
        except Exception: pass
    return P
A={os.path.basename(d):load(d) for d in sorted(glob.glob(f"{S}/xmodel/out/*")) if os.path.isdir(d)}
A={k:v for k,v in A.items() if len(v)>=50}
ts_all=sorted(t for t in set.intersection(*[set(v) for v in A.values()]) if t in D and all(t in s for s in subs))
print("各模型题数",{k:len(v) for k,v in A.items()},"共同",len(ts_all))
for k,P in A.items():
    ts=[t for t in P if t in D]; y=np.array([int(D[t]["passes"]<D[t]["runs"]) for t in ts]); p=np.array([P[t] for t in ts])
    pub=[t for t in ts if all(t in s for s in subs)]; pp=np.array([P[t] for t in pub]); diff=np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in pub])
    au=np.mean([roc_auc_score([0 if s[t]["resolved"] else 1 for t in pub],pp) for s in subs])
    print(f"{k:16s} n={len(ts)} DS挂{y.sum():2d}  DS AUC {roc_auc_score(y,p):.3f}  | 公开 n={len(pub)} 相关 {spearmanr(pp,diff)[0]:+.3f} 14家AUC {au:.3f}  平均p_fail {p.mean():.2f}")
# 共同题上
y=np.array([int(D[t]["passes"]<D[t]["runs"]) for t in ts_all])
print("共同题",len(ts_all),"DS挂",y.sum(),{k:round(roc_auc_score(y,[A[k][t] for t in ts_all]),3) for k in A})
diff=np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts_all])
rng=np.random.default_rng(0); B=[rng.integers(0,len(ts_all),len(ts_all)) for _ in range(2000)]
for k in A:
    p=np.array([A[k][t] for t in ts_all]); bs=[spearmanr(p[i],diff[i])[0] for i in B]
    print(f"  共同题 {k:16s} 相关 {spearmanr(p,diff)[0]:+.3f} 95%区间 {np.round(np.percentile(bs,[2.5,97.5]),2)}")
