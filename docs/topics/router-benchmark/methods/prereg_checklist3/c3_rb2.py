#!/usr/bin/env python3
"""预注册清单（3 条）在 rebench 100 道上的事前标注（与旧题标注逐字使用同一套提示：checklist5.py 的 5 规则提示取 r2、r5；c5b.py 的收窄成对提示取 pair）。
输入只有题面 + 动手前档案，不读任何 DS 结果。输出 out_c3_rb2/<task>.json。用法：c3_rb2.py run"""
import sys, json, os, glob
import v4 as V
ROOT = V.ROOT; S = V.S; O = ROOT / "out_c3_rb2"; O.mkdir(exist_ok=True)
ISS = {p.stem: p.read_text() for p in (S / "rebench/issue").glob("*.md")}
ALL = sorted(p.stem for p in (ROOT / "out_dossier_rb").glob("*.md"))
RULES = [
 ("R1", "期望行为没有明确定论", "题面没给确切的期望输出、异常类型、消息或接口形状，要靠推断（有复现与期望输出则为 0）"),
 ("R2", "没有可对照的现有测试，或与题面冲突", "档案里找不到能约束新行为的现有断言，或现有测试固化了与题面期望相反的行为"),
 ("R3", "题面自带误导线索", "题面的补丁、平台字样（如 on Windows）、链接或修法建议，可能把人带到错的位置或缩小范围"),
 ("R4", "只讲一侧，成对的另一侧可能也被测", "读/写、序列化/反序列化、TLS/非 TLS、开/关等成对情形，题面只提其中一侧"),
 ("R5", "修法需要按条件区分情形", "需要条件守卫或分支（不同类型、状态、平台走不同处理），而不是无条件改一处")]
P5 = """判断下面这道新题是否触发每条规则（1=触发，0=未触发）。只依据题面与动手前档案，不要使用对上游修法的记忆。保守：证据不足就判 0。
{rules}
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
只输出一行 JSON：{{"r1":0或1,"r2":0或1,"r3":0或1,"r4":0或1,"r5":0或1}}"""
PB = """判断下面这道新题是否同时满足以下两点（1=满足，0=不满足）。只依据题面与动手前档案，不要使用对上游修法的记忆。保守：证据不足就判 0。
(a) 存在「成对的两侧」（如读/写、序列化/反序列化、编码/解码、TLS/非 TLS、新增/删除、前向/反向），并且两侧在代码里是各自独立的实现（不是共用同一处逻辑改一次就同时生效）；
(b) 题面或建议的修法只明确点了其中一侧，另一侧要靠自己想到。
===== 完整题面 =====
{issue}
===== 动手前仓库档案 =====
{dos}
只输出一行 JSON：{{"pair":0或1,"why":"一句话（≤40字）"}}"""
def f(t):
    if (O / f"{t}.json").exists(): return t, "skip"
    iss = ISS[t][:6000]; dos = (ROOT / "out_dossier_rb" / f"{t}.md").read_text()
    try:
        rt = "\n".join(f"{i} {n}：{d}" for i, n, d in RULES)
        a = V.claude(P5.format(rules=rt, issue=iss, dos=dos), "claude-haiku-5-5", "r1"); b = V.claude(PB.format(issue=iss, dos=dos), "claude-haiku-5-5", "pair")
        r = {"r2": int(a["r2"]), "r5": int(a["r5"]), "r4": int(b["pair"])}
    except Exception as e: return t, f"err {e}"
    (O / f"{t}.json").write_text(json.dumps(r)); return t, "ok"
V.run(ALL, f, 6)
