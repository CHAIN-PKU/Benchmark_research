"""_examples（godog 的独立 Go 模块）名单外审计：把某次评测的 fix 日志与基线对比，列出「基线通过、这次失败或消失」的测试。
用法：python3 audit_examples.py <基线日志> <评测日志>      基线 = 打了测试补丁、未打答案时 _examples 的 go test -json 输出
"""
import json, sys


def results(path):
    last = {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("Test") and d.get("Action") in ("pass", "fail", "skip") and "/_examples" in d.get("Package", ""):
            last[f"{d['Package']}::{d['Test']}"] = d["Action"]
    return last


base, run = results(sys.argv[1]), results(sys.argv[2])
regressed = sorted(k for k, v in base.items() if v == "pass" and run.get(k) != "pass")
print(json.dumps({"baseline_tests": len(base), "baseline_pass": sum(v == "pass" for v in base.values()),
                  "run_tests": len(run), "run_pass": sum(v == "pass" for v in run.values()),
                  "regressed": regressed}, ensure_ascii=False))
sys.exit(1 if regressed else 0)
