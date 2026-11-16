#!/usr/bin/env python3
import json, pathlib, re, collections, hashlib, datetime
W=pathlib.Path("/home/ubuntu/benchmark_router_paper/e3_exp")
TASKS=json.load(open(W/"e3_tasks.json"))["tasks"]
CARD=(W/"ds_card_v2.md").read_text()
RB=pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/predictor_rebench")
REBENCH=set(json.load(open(RB/"tasks.json"))) if (RB/"tasks.json").exists() else set()
RUNS=pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot/runs")
EXT_LANG={".go":"go",".py":"python",".php":"php",".rb":"ruby",".java":"java",".kt":"java",".rs":"rust",
          ".c":"c",".h":"c",".cc":"c",".cpp":"c",".hpp":"c",".ts":"node",".tsx":"node",".js":"node",".jsx":"node",".mjs":"node",".vue":"node"}
NORM={"node":"node","javascript":"node","typescript":"node","go":"go","python":"python","php":"php","ruby":"ruby",
      "java":"java","java_maven":"java","java_gradle":"java","rust":"rust","c":"c","c_mp":"c","c++":"c"}
hist=[]
for d in RUNS.iterdir():
    if not d.is_dir() or d.name in REBENCH: continue
    recs=[]
    for r in (1,2):
        p=d/f"dsh_r{r}"/"record.json"
        if p.exists():
            try: x=json.loads(p.read_text())
            except: continue
            if x.get("hint"): continue
            recs.append(x)
    vals=[x.get("resolved") for x in recs if x.get("resolved") is not None]
    if not vals: continue
    hist.append({"task":d.name,"lang":NORM.get(recs[0].get("lang") or "?",recs[0].get("lang") or "?"),
                 "pass":1 if any(vals) else 0})
by=collections.defaultdict(lambda:[0,0,[]])
for h in hist:
    by[h["lang"]][0]+=h["pass"]; by[h["lang"]][1]+=1
    if not h["pass"]: by[h["lang"]][2].append(h["task"])
LANG_CSV={}
def load_lang_csv():
    import csv
    p=pathlib.Path("/home/ubuntu/benchmark_router_paper/e3_exp/e3_lang.csv")
    if p.exists():
        for r in csv.DictReader(open(p)): LANG_CSV[r["task"]]=r["lang"]
def infer_lang(issue, ev, task=None):
    if task and task in LANG_CSV: return LANG_CSV[task]
    txt=(issue or "")+"\n"+"\n".join(ev if isinstance(ev,list) else [str(ev)])
    c=collections.Counter()
    for m in re.finditer(r"[\w./-]+(\.[a-zA-Z0-9]{1,4})\b", txt):
        ext=m.group(1).lower()
        if ext in EXT_LANG: c[EXT_LANG[ext]]+=1
    return c.most_common(1)[0][0] if c else "other"
def old_issue(t):
    for d in ("predictor_prosp/issue","predictor_xmodel/issue"):
        p=pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval")/d/f"{t}.md"
        if p.exists(): return " ".join(p.read_text(errors="ignore").split())[:160]
    return ""
def sections(task, issue, ev):
    lang=infer_lang(issue, ev, task)
    n=len(hist); ps=sum(h["pass"] for h in hist)
    out=[f"### 语言先验（来自 {n} 道旧题真实标签，不含本批新题）",
         f"- 全部旧题：{ps}/{n} = {ps/n:.0%} 通过（挂率 {1-ps/n:.0%}）。"]
    if lang in by and by[lang][1]>=15:
        p,c,_=by[lang]; out.append(f"- 本题语言「{lang}」：{p}/{c} = {p/c:.0%} 通过（{c} 道样本）。")
    else:
        out.append(f"- 本题语言「{lang}」历史样本<15 道，用全部旧题先验，不单独下调。")
    fails=[h for h in hist if not h["pass"] and h["lang"]==lang and old_issue(h["task"])] if lang in by else []
    fails.sort(key=lambda h:h["task"])
    out.append("### 同语言旧题挂题短案例（只作对照，不要照抄）")
    for h in fails[:3]:
        out.append(f"- [{h['task']}] 题面大意：{old_issue(h['task'])} … → 该题 DeepSeek 两次都挂。")
    if len(fails)==0: out.append("- （该语言没有足够旧挂题，按经验卡条件判断即可。）")
    return "\n".join(out)
def build(task, issue, ev):
    evs="\n".join(f"- {e}" for e in ev)
    return f"""你是「动手前预测器」的判断环节。另一位调查员已经在仓库里查过这道题，下面是题面和它找到的证据（只有证据，没有它的结论）。
请只根据题面、这些证据和下面关于这个智能体的资料，判断编程智能体 DeepSeek 修好这道题并通过维护者隐藏测试的难度，给出失败概率。不要使用对上游修法的记忆。
请列出影响难度的主要因素（每条说明方向和分量），再给出失败概率。只输出一行 JSON：{{"task":"{task}","factors":[{{"factor":"影响难度的因素（≤20字）","direction":"更难/更容易","weight":"大/中/小"}}],"main_reason":"一句话说清最关键的判断依据（≤60字）","p_fail":0~1}}

===== 关于这个智能体的经验卡 =====
{CARD}

{sections(task, issue, ev)}

===== 题面 =====
{issue[:6000]}
===== 调查员找到的证据 =====
{evs}
"""
def main():
    load_lang_csv()
    bundle={}
    for line in open(W/"bundle.jsonl"):
        r=json.loads(line); bundle[r["task"]]=r
    (W/"prompts").mkdir(exist_ok=True)
    rows=[]; langs={}
    for t in TASKS:
        r=bundle.get(t)
        if not r: rows.append({"task":t,"status":"missing_bundle"}); continue
        issue=r.get("issue",""); ev=r.get("evidence",[])
        txt=build(t,issue,ev); p=W/"prompts"/f"{t}.txt"; p.write_text(txt)
        langs[t]=infer_lang(issue,ev,t)
        rows.append({"task":t,"status":"ok","lang":langs[t],"sha256":hashlib.sha256(txt.encode()).hexdigest(),
                     "written_at":datetime.datetime.now().strftime("%F %T")})
    json.dump(rows, open(W/"e3_ledger.json","w"), ensure_ascii=False, indent=1)
    print("built", sum(1 for r in rows if r["status"]=="ok"), "/", len(TASKS))
    print("langs", collections.Counter(langs.values()))
if __name__=="__main__": main()
