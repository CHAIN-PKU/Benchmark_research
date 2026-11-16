# 预测者之间为什么有差异：同题同输入。看 ①子风险分各自的准度 ②p_fail 是否用好了自己的子风险分 ③尺度 ④查证量
import json,glob,os,numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict
S=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D=json.load(open(f"{S}/tagging/tag_data.json")); subs=[json.load(open(f)) for f in glob.glob(f"{S}/pubhist/ml_*.json")]
def load(m):
    R={}
    for f in glob.glob(f"{S}/xmodel/out/{m}/*.json"):
        try: r=json.load(open(f)); float(r["p_fail"]); R[r["task"]]=r
        except Exception: pass
    return R
M={m:load(m) for m in ("sonnet_ref","ds","glm","jev")}
ts=sorted(t for t in set.intersection(*[set(v) for v in M.values()]) if t in D and all(t in s for s in subs))
diff=np.array([np.mean([0 if s[t]["resolved"] else 1 for s in subs]) for t in ts]); y=np.array([int(D[t]["passes"]<D[t]["runs"]) for t in ts])
print("共同题",len(ts),"DS挂",y.sum())
K=["risk_hidden","risk_narrow","risk_sibling","n_files_est"]
for m,R in M.items():
    X=np.array([[float(R[t].get(k,0) or 0) for k in K] for t in ts]); p=np.array([float(R[t]["p_fail"]) for t in ts])
    ev=np.mean([len(R[t].get("evidence",[])) for t in ts]); turns=np.nanmean([R[t].get("_turns") or np.nan for t in ts])
    sub=" ".join(f"{k[5:] if k.startswith('risk') else 'files'} {spearmanr(X[:,i],diff)[0]:+.2f}" for i,k in enumerate(K))
    # 用自己的子风险分、在难度上做最优组合（留一交叉）能到多少 → 与它自己的 p_fail 比：p_fail 是否用好了自己看到的东西
    Z=(X-X.mean(0))/(X.std(0)+1e-9); yy=(diff>np.median(diff)).astype(int)
    q=cross_val_predict(LogisticRegression(C=1),Z,yy,cv=10,method="decision_function")
    print(f"{m:11s} p_fail相关 {spearmanr(p,diff)[0]:+.2f} | 子分相关: {sub} | 子分最优组合 {spearmanr(q,diff)[0]:+.2f} | 平均p {p.mean():.2f} 标准差 {p.std():.2f} | 轮数 {turns:.0f}")
# 查：各家子分之间是否看见同样的风险（与 Sonnet 的子分相关）
for m in ("ds","glm","jev"):
    print(m,"与 Sonnet 同题子分一致度:",{k[5:]:round(spearmanr([float(M[m][t].get(k,0) or 0) for t in ts],[float(M['sonnet_ref'][t].get(k,0) or 0) for t in ts])[0],2) for k in K[:3]},
          "p_fail 一致度", round(spearmanr([M[m][t]['p_fail'] for t in ts],[M['sonnet_ref'][t]['p_fail'] for t in ts])[0],2))
