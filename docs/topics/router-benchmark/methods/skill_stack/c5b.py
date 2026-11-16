#!/usr/bin/env python3
"""收窄版 R4：成对的两侧是两份独立代码（各有自己的实现，不共享同一处逻辑），且题面/修法建议只点了其中一侧。保守：证据不足判 0。"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; D = V.D; O = ROOT / "out_c5b"; O.mkdir(exist_ok=True)
P = """判断下面这道新题是否同时满足以下两点（1=满足，0=不满足）。只依据题面与动手前档案，不要使用对上游修法的记忆。保守：证据不足就判 0。
(a) 存在「成对的两侧」（如读/写、序列化/反序列化、编码/解码、TLS/非 TLS、新增/删除、前向/反向），并且两侧在代码里是各自独立的实现（不是共用同一处逻辑改一次就同时生效）；
(b) 题面或建议的修法只明确点了其中一侧，另一侧要靠自己想到。
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
只输出一行 JSON：{{"pair":0或1,"why":"一句话（≤40字）"}}"""
ALL = sorted(os.path.basename(f)[:-3] for f in glob.glob(str(ROOT / "out_dossier/*.md")) if os.path.basename(f)[:-3] in D)
def f(t):
    if (O / f"{t}.json").exists(): return t, "skip"
    try: r = V.claude(P.format(issue=D[t]["issue"][:6000], dos=V.DOS(t)), "claude-haiku-5-5", "pair"); r["pair"] = int(r["pair"])
    except Exception as e: return t, f"err {e}"
    (O / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
V.run(ALL, f, 6)
