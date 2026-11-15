"""用法：python analyze.py <tag_data.json> <下载的 ml_*.json 所在目录>"""
import json, glob, os, sys, numpy as np
from sklearn.metrics import roc_auc_score
d = json.load(open(sys.argv[1]))
subs = {os.path.basename(f)[3:-5]: json.load(open(f)) for f in glob.glob(sys.argv[2] + "/ml_*.json")}
ts = [t for t in d if all(t in s for s in subs.values())]
y = np.array([int(d[t]["passes"] < d[t]["runs"]) for t in ts]); ys = np.array([int(d[t]["passes"] == 0) for t in ts])
ss = [v for k, v in subs.items() if "deepseek" not in k]
p = np.array([1 - np.mean([bool(s[t].get("resolved")) for s in ss]) for t in ts])
print(len(ts), "tasks", len(ss), "subs; loose AUC", round(roc_auc_score(y, p), 3), "strict AUC", round(roc_auc_score(ys, p), 3))
