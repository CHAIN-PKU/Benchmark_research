#!/usr/bin/env python3
"""从 .err 里保存的模型原文中重新解析 JSON（不重跑模型）。成功则写 <task>.json（_rescued=true），.err 改名 .err.rescued。
用法：python3 rescue_err.py out/<tag> [...]"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from run_predictor import extract
for d in map(pathlib.Path, sys.argv[1:]):
    ok = bad = 0
    for e in sorted(d.glob("*.err")):
        task = e.stem
        if (d / f"{task}.json").exists():
            e.rename(e.with_suffix(".err.stale")); continue
        body = e.read_text()
        raw = body.split("----- raw -----\n", 1)[-1].split("\nrc=", 1)[0]
        try:
            row = extract(raw)
        except Exception:
            bad += 1; continue
        row.update(task=task, _rescued=True)
        (d / f"{task}.json").write_text(json.dumps(row, ensure_ascii=False) + "\n")
        e.rename(e.with_suffix(".err.rescued")); ok += 1
    print(d.name, "rescued", ok, "still_err", bad)
