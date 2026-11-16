#!/usr/bin/env python3
"""单个学生（DS）的「难度校正后画像」：残差 = 真实挂(0/1) − 判断者概率（Sonnet，用训练折 Platt 校准前的原始 p 的 logit 回归掉难度）。
每个技能项的画像值 = Q 加权的平均残差（正=该技能上 DS 比判断者预期更容易挂）。
可学性诊断：按仓库随机分两半 200 次，看两半画像向量的相关（split-half reliability）。接近 0 = 数据量学不出稳定的单模型画像。"""
import json, glob, os, numpy as np
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
R = os.path.dirname(os.path.abspath(__file__)); S = os.path.dirname(R)
D = json.load(open(f"{S}/tagging/tag_data.json")); tax = json.load(open(f"{R}/out_tax/taxonomy.json"))["skills"]; ids = [s["id"] for s in tax]
Q = {os.path.basename(f)[:-5]: json.load(open(f)) for f in glob.glob(f"{R}/out_tax/q/*.json")}
J = {json.load(open(f))["task"]: float(json.load(open(f))["p_fail"]) for f in glob.glob(f"{R}/out_judge_full/dos_sonnet/*.json")}
ts = sorted(t for t in Q if t in D and t in J); y = np.array([int(D[t]["passes"] < D[t]["runs"]) for t in ts])
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
p = LogisticRegression(C=10).fit(lg(np.array([J[t] for t in ts]))[:, None], y).predict_proba(lg(np.array([J[t] for t in ts]))[:, None])[:, 1]
res = y - p; X = np.array([[Q[t][i] for i in ids] for t in ts]); W = X / X.sum(0)
prof = W.T @ res
print("DS 难度校正后的单模型画像（正=比判断者预期更容易挂）")
for s, v in sorted(zip(tax, prof), key=lambda a: -abs(a[1])): print(f"  {s['id']:4s} {s['name']:10s} {v:+.3f}")
repos = sorted({D[t]["repo"] for t in ts}); rng = np.random.default_rng(0); rs = []
for _ in range(300):
    pick = set(rng.permutation(repos)[: len(repos) // 2]); a = np.array([D[t]["repo"] in pick for t in ts])
    pa = (X[a] / X[a].sum(0)).T @ res[a]; pb = (X[~a] / X[~a].sum(0)).T @ res[~a]; rs.append(spearmanr(pa, pb)[0])
print(f"\n分半可靠性：两半画像向量的秩相关 均值 {np.mean(rs):+.2f}，区间 [{np.percentile(rs,2.5):+.2f}, {np.percentile(rs,97.5):+.2f}]（n={len(ts)}，挂 {y.sum()}）")
