#!/bin/bash
# 用法：eval_once.sh <标签> <补丁文件>   每次评测用新目录，评测后给日志和报告打 SHA256SUMS
set -euo pipefail
cd "$(dirname "$0")"
TAG="$1"; PATCH="$2"; R="runs/$TAG"
mkdir -p "$R/work" "$R/out" "$R/logs" repos
./venv/bin/python run_eval.py --mode evaluation --workdir "$R/work" --patch_files "$PATCH" \
  --dataset_files dataset_godog.jsonl --output_dir "$R/out" --log_dir "$R/logs" --repo_dir repos \
  --stop_on_error true --max_workers 1 --max_workers_build_image 1 --max_workers_run_instance 1 \
  --log_level INFO > "$R/harness_stdout.log" 2>&1
( cd "$R" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
echo "done $R"
