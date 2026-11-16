#!/bin/bash
WK=${1:-0}; NW=${2:-2}
cd /home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot
export RB_CHANNEL=dsh RB_DSH_PORT=8766
PY=/home/ubuntu/ai-market/venv/bin/python3
LOG=/tmp/gate77b_w${WK}.log
mapfile -t TASKS < /tmp/test77.txt
echo "[$(date +%T)] w$WK n=${#TASKS[@]}" >> "$LOG"
i=0
for t in "${TASKS[@]}"; do
  [ -z "$t" ] && continue
  if [ $((i % NW)) -ne "$WK" ]; then i=$((i+1)); continue; fi
  i=$((i+1))
  [ -e STOP ] && exit 0
  if [ -e "runs/$t/dsh_r1/record.json" ] || [ -e "runs/$t/dsh_r2/record.json" ]; then continue; fi
  if [ ! -e "runs/$t/selfcheck/selfcheck.json" ]; then
    echo "[$(date +%T)] w$WK check $t" >> "$LOG"
    timeout 3600 $PY ds_pilot.py check "$t" >> "$LOG" 2>&1
  fi
  if [ ! -e "runs/$t/selfcheck/selfcheck.json" ]; then
    echo "[$(date +%T)] w$WK check-fail $t" >> "$LOG"; continue
  fi
  rep=""
  for r in 1 2; do [ -e "runs/$t/dsh_r$r" ] || { rep=$r; break; }; done
  [ -z "$rep" ] && continue
  [ -d "/home/coder/chains/rb_dsh__${t}__r$rep" ] && sudo rm -rf "/home/coder/chains/rb_dsh__${t}__r$rep"
  echo "[$(date +%T)] w$WK run $t r$rep" >> "$LOG"
  timeout 3000 $PY ds_pilot.py run "$t" "$rep" >> "$LOG" 2>&1
  echo "[$(date +%T)] w$WK done $t r$rep" >> "$LOG"
done
