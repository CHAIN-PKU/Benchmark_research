#!/bin/bash
# 方法 3（结构化取证）与方法 5（通用提示多次采样）在前瞻 123 道上的预测；跑完统一冻结
cd "$(dirname "$0")"
export PRED_KEEP_HOME=1 ANTHROPIC_MODEL=claude-sonnet-5-5
PRED_CHECKLIST=structured_v1.md python3 run_predictor.py sonnet_struct --jobs 3 > m3.log 2>&1
PRED_CHECKLIST=generic_plain.md python3 run_predictor.py sonnet_gen_s2 --jobs 3 > m5a.log 2>&1
PRED_CHECKLIST=generic_plain.md python3 run_predictor.py sonnet_gen_s3 --jobs 3 > m5b.log 2>&1
PRED_CHECKLIST=structured_v1.md python3 run_predictor.py sonnet_struct --jobs 2 >/dev/null 2>&1  # 补跑失败题（已有结果的跳过）
for a in sonnet_gen_s2 sonnet_gen_s3; do PRED_CHECKLIST=generic_plain.md python3 run_predictor.py $a --jobs 2 >/dev/null 2>&1; done
python3 - <<'PY'
import json,glob,hashlib,datetime
rows=[]
for a in ("sonnet_struct","sonnet_gen_s2","sonnet_gen_s3"):
    for f in sorted(glob.glob(f"out/{a}/*.json")):
        r=json.load(open(f)); rows.append({"arm":a,**{k:r.get(k) for k in ("task","p_fail","n_sites","n_sites_unmentioned","n_cases_unexampled","n_conflicts")}})
open("m35_frozen.jsonl","w").write("".join(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n" for r in rows))
h=hashlib.sha256(open("m35_frozen.jsonl","rb").read()).hexdigest()
open("m35_frozen.sha256","w").write(f"{h}  m35_frozen.jsonl  {datetime.datetime.now().isoformat(timespec='seconds')}\n")
print(len(rows),h)
PY
