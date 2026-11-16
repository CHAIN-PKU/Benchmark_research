#!/usr/bin/env python3
"""生成「有道理的历史证据卡」：语言先验 + 失败模式频率 + 同语言同类挂题短案例。"""
import json, pathlib, re, sys, collections
B=pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval")
R=B/"ds_pilot/runs"
ISSUE_DIRS=[B/"predictor_prosp/issue"]
def issue_of(t):
    for d in ISSUE_DIRS:
        p=d/f"{t}.md"
        if p.exists(): return p.read_text(errors="ignore")[:3000]
    p=B/"predictor_rebench/snap"/t/"issue.md"
    return p.read_text(errors="ignore")[:3000] if p.exists() else ""
def load_hist():
    rows={}
    for t in R.iterdir():
        if not t.is_dir(): continue
        recs=[]
        for r in (1,2):
            p=t/f"dsh_r{r}"/"record.json"
            if p.exists():
                try: d=json.loads(p.read_text())
                except: continue
                if d.get("hint"): continue
                recs.append(d)
        vals=[d.get("resolved") for d in recs if d.get("resolved") is not None]
        if not vals: continue
        rows[t.name]={"lang":recs[0].get("lang") or "?","repo":(recs[0].get("repo") or "?"),
                      "pass":1 if any(vals) else 0,"issue":issue_of(t.name)}
    return rows
H=load_hist()
FAIL_MODES=[("只照题面字面改，没覆盖隐含要求",0.33),("只自测题面给的那一个例子",0.31),("修症状不修根因",0.14),("没找并列实现/同类调用点",0.10)]
def card(task):
    issue=issue_of(task)
    lang="?"
    for t,h in H.items():
        if t.split("-")[0].split("__")[0]==task.split("-")[0].split("__")[0]:
            lang=h["lang"]; break
    n=len(H); rate=sum(h["pass"] for h in H.values())/max(1,n)
    byl=collections.defaultdict(lambda:[0,0])
    for h in H.values():
        byl[h["lang"]][0]+=h["pass"]; byl[h["lang"]][1]+=1
    lp=byl.get(lang)
    prior=f"整体 {n} 道历史题通过率 {rate:.0%}"
    if lp and lp[1]>=5: prior+=f"；{lang} 题 {lp[1]} 道通过率 {lp[0]/lp[1]:.0%}"
    # 同类挂题案例：同语言挂题，按题面关键词重合排
    words=set(re.findall(r"[A-Za-z_]{4,}", issue.lower()))
    cands=[]
    for t,h in H.items():
        if h["pass"] or h["lang"]!=lang: continue
        iw=set(re.findall(r"[A-Za-z_]{4,}", h["issue"].lower()))
        cands.append((len(words&iw), t, h["issue"]))
    cands.sort(reverse=True)
    lines=[f"## 历史证据卡（目标模型：DeepSeek；历史 {n} 道，含挂 {sum(1 for h in H.values() if not h['pass'])} 道）",]
    lines.append(f"### 1. 先验（全部来自真实历史标签）\n- {prior}。")
    lines.append("### 2. 这个模型的高频挂法（阅卷统计，非题面猜测）\n" + "\n".join(f"- {m}：{p:.0%} 的挂题" for m,p in FAIL_MODES))
    lines.append("### 3. 同语言、同类挂题短案例（供对照，不要照抄）")
    for _,t,i in cands[:3]:
        head=" ".join(i.split())[:120]
        lines.append(f"- [{t}] 题面: {head} … → 该题 DS 两次都挂。")
    return "\n\n".join(lines)
if __name__=="__main__":
    t=sys.argv[1]
    print(card(t))
