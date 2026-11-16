# 挂题内部：真实踩的那个坑，在判断者的逐坑概率里排第一的比例（随机基线 = 1/坑数）
import json,glob,os,numpy as np
R=os.path.dirname(os.path.abspath(__file__))
L={os.path.basename(f)[:-5]:set(json.load(open(f)).get("fell",[])) for f in glob.glob(R+"/out_pit/label/*.json")}
for arm in ("nohist","hist"):
    top=[];base=[]
    for t,fell in L.items():
        if not fell: continue
        f=f"{R}/out_pit/judge_{arm}_haiku/{t}.json"
        if not os.path.exists(f): continue
        pp={int(p["id"]):float(p["p"]) for p in json.load(open(f)).get("per_pit",[])}
        if not pp: continue
        m=max(pp.values()); top.append(any(pp.get(i,-1)==m for i in fell)); base.append(len(fell)/len(pp))
    print(arm,"n",len(top),"真实坑排第一（含并列）%.2f"%np.mean(top),"随机 %.2f"%np.mean(base))
