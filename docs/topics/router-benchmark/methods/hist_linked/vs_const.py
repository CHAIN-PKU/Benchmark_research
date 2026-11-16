# 基线检验（crc 19:49）：只报历史通过率（常数预测，等价于按历史概率掷骰子）vs 各判断做法。常数用另一折失败率。
import json,glob,os,numpy as np
from sklearn.metrics import roc_auc_score
R=os.path.dirname(os.path.abspath(__file__)); S=os.path.dirname(R)
D=json.load(open(f"{S}/tagging/tag_data.json")); FO=json.load(open(f"{S}/refjudge/repo_fold.json"))
def load(d):
    P={}
    for f in glob.glob(f"{R}/{d}/*.json"):
        try: r=json.load(open(f)); P[r["task"]]=float(r["p_fail"])
        except Exception: pass
    return P
lg=lambda p:np.log(np.clip(p,1e-3,1-1e-3)/(1-np.clip(p,1e-3,1-1e-3))); sg=lambda z:1/(1+np.exp(-z))
ARMS={"档案+Haiku":"out_judge_full/dos_haiku","档案+Sonnet":"out_judge_full/dos_sonnet","Haiku+偏失败文案":"out_hdoc/judge_haiku","Sonnet+偏失败文案":"out_hdoc/judge_sonnet","Haiku+先列有利":"out_hdoc/proscons_haiku"}
ts=None; A={k:load(v) for k,v in ARMS.items()}
ts=sorted(set.intersection(*[set(p) for p in A.values()])&{t for t in D if D[t]["repo"] in FO})
y=np.array([int(D[t]["passes"]<D[t]["runs"]) for t in ts]); fo=np.array([FO[D[t]["repo"]] for t in ts])
const=np.zeros(len(ts)); 
for f in set(fo): const[fo==f]=y[fo!=f].mean()
rng=np.random.default_rng(0); B=[rng.integers(0,len(ts),len(ts)) for _ in range(2000)]
br=lambda p,i=slice(None):np.mean((p[i]-y[i])**2)
print(f"n={len(ts)} DS挂{y.sum()}  常数（历史通过率）Brier {br(const):.4f}  AUC 0.500（不能排序）  ← 基线")
for k,P in A.items():
    p=np.array([P[t] for t in ts]); c=np.zeros_like(p)
    for f in set(fo):
        tr=fo!=f; z=lg(p[tr]); s=0.
        for _ in range(300): s+=(y[tr].mean()-sg(z+s).mean())*4
        c[fo==f]=sg(lg(p[fo==f])+s)
    d=[br(c,i)-br(const,i) for i in B]; a=[roc_auc_score(y[i],p[i]) for i in B if len(set(y[i]))==2]
    print(f"{k:18s} 校准后 Brier {br(c):.4f} (比常数 {br(c)-br(const):+.4f} 区间 {np.round(np.percentile(d,[2.5,97.5]),3)})  AUC {roc_auc_score(y,p):.3f} 区间 {np.round(np.percentile(a,[2.5,97.5]),2)}")
