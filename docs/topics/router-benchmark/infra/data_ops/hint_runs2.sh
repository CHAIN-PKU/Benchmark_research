#!/bin/bash
# 干预实验第二轮：给还缺第 2 次带纸条运行的题补跑
WK=${1:-0}; NW=${2:-2}
cd /home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot
export RB_CHANNEL=dsh RB_DSH_PORT=8766
PY=/home/ubuntu/ai-market/venv/bin/python3
LOG=/tmp/hint2_w${WK}.log
$PY - <<'PY' > /tmp/hint2_missing.txt
import json,pathlib
sel=json.load(open("selection.json")); tasks=sel["fail"]+sel["pass"]
miss=[]
for t in tasks:
    d=pathlib.Path("runs")/t
    n=sum(1 for r in (3,4,5,6) if (d/f"dsh_r{r}"/"record.json").exists())
    if n<2: miss.append(t)
print("\n".join(miss))
PY
mapfile -t TASKS < /tmp/hint2_missing.txt
echo "[$(date +%T)] w$WK n=${#TASKS[@]}" >> "$LOG"
i=0
for t in "${TASKS[@]}"; do
  [ -z "$t" ] && continue
  if [ $((i % NW)) -ne "$WK" ]; then i=$((i+1)); continue; fi
  i=$((i+1))
  [ -e STOP ] && exit 0
  rep=""
  for r in 3 4 5 6; do [ -e "runs/$t/dsh_r$r" ] || { rep=$r; break; }; done
  [ -z "$rep" ] && continue
  [ -d "/home/coder/chains/rb_dsh__${t}__r$rep" ] && sudo rm -rf "/home/coder/chains/rb_dsh__${t}__r$rep"
  echo "[$(date +%T)] w$WK run $t r$rep" >> "$LOG"
  $PY ds_pilot.py run "$t" "$rep" >> "$LOG" 2>&1
  echo "[$(date +%T)] w$WK done $t r$rep" >> "$LOG"
done
