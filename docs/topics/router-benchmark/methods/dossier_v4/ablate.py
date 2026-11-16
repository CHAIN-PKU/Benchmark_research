#!/usr/bin/env python3
"""删节实验：把仓库档案的第 k 节删掉（k=1..7），其余不变，用同一判断提示判一遍，看哪一节决定准度。
另有 only_k：只保留第 k 节（加题面）。用法：ablate.py <drop|only> <k> <模型> [--jobs N]"""
import sys, json, re, pathlib
import v4 as V
ROOT = V.ROOT; D = V.D
mode, k, model = sys.argv[1], int(sys.argv[2]), sys.argv[3]
jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
short = model.replace("claude-", "").replace("-5-5", "")
out = ROOT / "out_ablate" / f"{mode}{k}_{short}"; out.mkdir(parents=True, exist_ok=True)
ALL = sorted(p.stem for p in (ROOT / "out_dossier").glob("*.md") if p.stem in D)
HDR = re.compile(r"(?m)^(?:\*\*)?\s*(?:#+\s*)?(?:【\s*([1-7])[^】\n]*】|([1-7])\s+[^\n]{0,20}$)")
def sections(txt):
    marks = [(m.start(), int(m.group(1) or m.group(2))) for m in HDR.finditer(txt)]
    seen, cut = set(), []
    for pos, n in marks:
        if n not in seen: seen.add(n); cut.append((pos, n))
    cut.sort(); parts = {}
    for i, (pos, n) in enumerate(cut):
        end = cut[i + 1][0] if i + 1 < len(cut) else len(txt)
        parts[n] = txt[pos:end]
    return parts
def edited(t):
    parts = sections(V.DOS(t))
    if len(parts) < 6: return None
    keep = [n for n in sorted(parts) if (n != k if mode == "drop" else n == k)]
    return "".join(parts[n] for n in keep)
def f(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    dos = edited(t)
    if dos is None: return t, "noparse"
    try:
        r = V.claude(V.JUDGE.format(agent=V.AGENT, cases="", issue=D[t]["issue"][:6000], dos=dos, ask=""), model, "p_fail")
    except Exception as e:
        return t, f"err {e}"
    r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
if __name__ == "__main__":
    if "--check" in sys.argv:
        c = sum(1 for t in ALL if edited(t) is not None); print(c, "/", len(ALL), "parsable"); sys.exit()
    V.run(ALL, f, jobs)
