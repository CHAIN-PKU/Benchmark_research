#!/usr/bin/env python3
"""rebench 100 道：针对每个执行者的事前预测（冻结后才放行该执行者开跑）。
输入：完整题面 + 仓库档案（out_dossier_rb）+ 执行者档案（只用开跑前可合法获得的信息）。
组别：blind（不告诉执行者是谁）/ DS / GLM / SONNET / HAIKU / KIMI。用法：rb_target.py <组> <判断模型> [--jobs N]"""
import sys, json, pathlib
import v4 as V
ROOT = V.ROOT; S = V.S
arm, model = sys.argv[1], sys.argv[2]
jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
short = model.replace("claude-", "").replace("-5-5", "")
out = ROOT / "out_rb_target" / f"{arm}_{short}"; out.mkdir(parents=True, exist_ok=True)
ISS = {p.stem: p.read_text() for p in (S / "rebench/issue").glob("*.md")}
ALL = sorted(p.stem for p in (ROOT / "out_dossier_rb").glob("*.md"))
PROFILE = {
 "blind": "一个编程智能体（不告诉你是哪个模型）",
 "DS": "编程智能体 DeepSeek v4.1 flash（便宜的开源模型）。我们的记录：在 265 道真实仓库旧题上约 79% 通过；操作记录显示它习惯照题面字面实现、通常只为题面给的例子写自测、较少去找并列实现",
 "GLM": "编程智能体 GLM-5.3x Flash（便宜的开源模型）。我们没有它在这类题上的历史记录；公开榜上同家族前代 GLM-5 在多语言真实仓库题上约 70% 通过",
 "SONNET": "编程智能体 Claude Sonnet 5.5（较贵的闭源模型）。我们没有它在这类题上的历史记录；公开榜上前代 Claude Sonnet 4.5 在多语言真实仓库题上约 67% 通过",
 "HAIKU": "编程智能体 Claude Haiku 5.5（便宜的闭源小模型）。我们没有它在这类题上的历史记录；公开榜上前代 Claude Haiku 4.5 在多语言真实仓库题上约 64% 通过",
 "KIMI": "编程智能体 Kimi K3.1 Pro（开源模型）。我们没有它在这类题上的历史记录；公开榜上前代 Kimi K2.5 在多语言真实仓库题上约 67% 通过",
}[arm]
def f(t):
    if (out / f"{t}.json").exists(): return t, "skip"
    dos = (ROOT / "out_dossier_rb" / f"{t}.md").read_text()
    try:
        r = V.claude(V.JUDGE.format(agent=PROFILE, cases="", issue=ISS[t][:6000], dos=dos, ask=""), model, "p_fail")
    except Exception as e:
        return t, f"err {e}"
    r["task"] = t; (out / f"{t}.json").write_text(json.dumps(r, ensure_ascii=False)); return t, "ok"
if __name__ == "__main__":
    V.run(ALL, f, jobs)
