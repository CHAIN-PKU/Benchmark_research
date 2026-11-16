#!/bin/bash
# 杀掉超过 65 分钟的 harbor 运行、超过 75 分钟的 ds_pilot 运行（避免卡死占机器）
now=$(date +%s)
for pid in $(pgrep -f "harbor run -p swe-rebench" ); do
  st=$(stat -c %Y /proc/$pid 2>/dev/null || echo $now)
  age=$((now - st))
  if [ $age -gt 3900 ]; then echo "[$(date +%T)] kill harbor $pid age=${age}s" >> /tmp/watchdog.log; kill -9 $pid 2>/dev/null; fi
done
for pid in $(pgrep -f "ds_pilot.py run "); do
  st=$(stat -c %Y /proc/$pid 2>/dev/null || echo $now)
  age=$((now - st))
  if [ $age -gt 4500 ]; then echo "[$(date +%T)] kill ds_pilot $pid age=${age}s" >> /tmp/watchdog.log; kill -9 $pid 2>/dev/null; fi
done
