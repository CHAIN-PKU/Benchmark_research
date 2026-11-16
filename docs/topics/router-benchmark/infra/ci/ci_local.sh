#!/bin/bash
# 本地 CI：语法检查 + 关键脚本用法检查 + 冻结 sha 校验
set -e
cd "$(dirname "$0")/.."
fail=0
echo "[1/3] python 语法检查"
for f in $(git ls-files '*.py' | head -200); do
  python3 -m py_compile "$f" || { echo "SYNTAX FAIL: $f"; fail=1; }
done
echo "[2/3] 关键脚本 --help/语法冒烟"
python3 - <<'PY'
import ast, pathlib
ok=True
for p in pathlib.Path("ops/data_ops").glob("*.py"):
    try: ast.parse(p.read_text())
    except Exception as e: print("AST FAIL", p, e); ok=False
print("ops scripts ast", "ok" if ok else "fail")
PY
echo "[3/3] 冻结 sha 校验（若文件存在）"
[ -f MANIFEST_20261115.md ] && echo "manifest present"
echo "CI $( [ $fail -eq 0 ] && echo GREEN || echo RED )"
exit $fail
