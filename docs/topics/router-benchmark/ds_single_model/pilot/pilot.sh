#!/bin/bash
# 3 道试跑：先全部自检，再每题 DS 跑 2 次（串行，避免余额差串账）
cd "$(dirname "$0")"
PY=~/ai-market/venv/bin/python3
T="caddyserver__caddy-6051 fluent__fluentd-4655 sharkdp__bat-2650"
for t in $T; do $PY ds_pilot.py check $t; done
for t in $T; do for r in 1 2; do
  [ -e STOP ] && { echo STOP; exit 0; }
  $PY ds_pilot.py run $t $r
done; done
echo PILOT_DONE
