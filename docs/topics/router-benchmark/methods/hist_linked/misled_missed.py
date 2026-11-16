#!/usr/bin/env python3
"""只用 DS 跑题成败 + 判断者输出（不用任何其他模型的成绩）。
对每个可见特征同时算：与「判断者给的 p_fail」的相关（判断者被它牵引多少）、与「DS 真实挂」的相关（它真实预示多少）。
  牵引大、真实小 = 判断者被误导；牵引小、真实大 = 判断者漏掉的信号。"""
import json, glob, os, re, numpy as np
from scipy.stats import spearmanr
R = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(R)
D = json.load(open(f"{S}/tagging/tag_data.json")); FO = json.load(open(f"{S}/refjudge/repo_fold.json"))
load = lambda d: {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(f"{R}/{d}/*.json")}
J = {"Sonnet": load("out_judge_full/dos_sonnet"), "Haiku": load("out_judge_full/dos_haiku")}
EXT = {os.path.basename(f)[:-5]: json.load(open(f))["pits"] for f in glob.glob(f"{R}/out_pit/extract/*.json")}
ts = sorted(t for t in EXT if t in D and all(t in j for j in J.values()))
dos = lambda t: open(f"{R}/out_dossier/{t}.md").read()
y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts])
def sec(t, n):
    m = re.search(rf"(?:【{n}[^】]*】|#+\s*{n}[^\n]*\n)(.*?)(?=【{n+1}|#+\s*{n+1}|\Z)", dos(t), re.S); return m.group(1) if m else ""
F = {
 "题面长度": lambda t: len(D[t]["issue"]), "题面含代码块/补丁": lambda t: int("```" in D[t]["issue"] or "--- a/" in D[t]["issue"]),
 "题面含修法建议词": lambda t: int(bool(re.search(r"(should|could|fix|patch|修|改成|应该)", D[t]["issue"], re.I))), "题面含报错/堆栈": lambda t: int(bool(re.search(r"(Traceback|panic|Exception|Error:|stack)", D[t]["issue"]))),
 "档案长度": lambda t: len(dos(t)), "档案坑数": lambda t: len(EXT[t]), "T1 边界坑数": lambda t: sum(p["type"] == "T1" for p in EXT[t]),
 "T2 并列坑数": lambda t: sum(p["type"] == "T2" for p in EXT[t]), "T3 约定坑数": lambda t: sum(p["type"] == "T3" for p in EXT[t]), "T4 题面误导坑数": lambda t: sum(p["type"] == "T4" for p in EXT[t]),
 "档案第6节（规模）长度": lambda t: len(sec(t, 6)), "档案第7节（难点）长度": lambda t: len(sec(t, 7)), "档案含「未核实/不确定」": lambda t: len(re.findall(r"未核|未确认|不确定|待核|推测", dos(t))),
 "档案称「只改一处/一行」": lambda t: int(bool(re.search(r"(只改一处|仅一行|一行改动|单点|1-3 行|3-5 行|几行)", dos(t)))), "标准修复行数": lambda t: len(D[t].get("gold", "").splitlines()),
}
print(f"n={len(ts)} DS挂{y.sum()}")
for jn, P in J.items():
    p = np.array([P[t] for t in ts]); print(f"\n== 判断者 {jn}（整体 AUC 对 DS = {__import__('sklearn.metrics', fromlist=['roc_auc_score']).roc_auc_score(y, p):.3f}）")
    print(f"{'特征':22s} 牵引(与p_fail)  真实(与DS挂)  差距   读法")
    rows = []
    for k, f in F.items():
        x = np.array([f(t) for t in ts], float)
        if x.std() == 0: continue
        a, b = spearmanr(x, p)[0], spearmanr(x, y)[0]; rows.append((k, a, b))
    for k, a, b in sorted(rows, key=lambda r: -(abs(r[1]) - abs(r[2]))):
        tag = "被牵引、不预示" if abs(a) - abs(b) > .12 else "预示、却没被用" if abs(b) - abs(a) > .08 else ""
        print(f"{k:22s} {a:+.2f}          {b:+.2f}        {abs(a)-abs(b):+.2f}  {tag}")
