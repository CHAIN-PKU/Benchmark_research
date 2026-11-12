"""表 1：四个 benchmark 框架对比（内容来自 docs/benchmark-frameworks.md）。
同时输出：booktabs 风格的预览图（out/fig_frameworks_table.*）和可直接 \\input 的 LaTeX（out/tab_frameworks.tex）。"""
import matplotlib.pyplot as plt

from style import ICML_FULL, OUT, STAGE, save

HEADER = ["Framework", "Task source", "Grading", "Leak / hack defense", "What we reuse"]
ROWS = [
    ["SWE-bench", "Real GitHub PRs + issues", "Fail-to-pass unit tests", "Grader outside the agent;\nVerified subset", "Real-source tasks,\nfrozen environments"],
    ["Inspect AI", "Dataset + solver + scorer", "Rules or model-graded", "Sandboxed execution", "Task structure,\nsandbox config"],
    ["lm-eval-harness", "YAML static tasks", "Log-likelihood /\nexact match", "n-gram decontamination", "Static-QA format,\ndecontamination"],
    ["BenchJack", "— (audit tool)", "—", "V1–V8 hackability checklist", "Pre-release audit"],
]
COL_X = [0.0, 0.15, 0.36, 0.55, 0.79]   # 每列左边界（0–1 归一化）

fig, ax = plt.subplots(figsize=(ICML_FULL, 1.75))
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")

top, header_h, row_h = 0.95, 0.13, 0.19
ax.axhline(top, color="#1F2A30", lw=1.2)
for x, h in zip(COL_X, HEADER):
    ax.text(x + 0.005, top - header_h / 2, h, ha="left", va="center", fontsize=7, fontweight="bold")
ax.axhline(top - header_h, color="#1F2A30", lw=0.6)
for r, row in enumerate(ROWS):
    yc = top - header_h - (r + 0.5) * row_h
    for c, (x, cell) in enumerate(zip(COL_X, row)):
        ax.text(x + 0.005, yc, cell, ha="left", va="center", fontsize=6.4, linespacing=1.15,
                fontweight="bold" if c == 0 else "normal",
                color=STAGE["build"][0] if c == 4 else "#1F2A30")
ax.axhline(top - header_h - len(ROWS) * row_h, color="#1F2A30", lw=1.2)
save(fig, "fig_frameworks_table")


def tex(s):
    return s.replace("\n", " ").replace("&", r"\&").replace("—", "---").replace("–", "--")


lines = [r"% 需要 \usepackage{booktabs,tabularx}；由 figures/gen_fig_frameworks_table.py 生成",
         r"\begin{table*}[t]", r"\centering", r"\small",
         r"\caption{Benchmark frameworks we build on.}", r"\label{tab:frameworks}",
         r"\begin{tabularx}{\textwidth}{@{}lXXXX@{}}", r"\toprule",
         " & ".join(rf"\textbf{{{tex(h)}}}" for h in HEADER) + r" \\", r"\midrule"]
lines += [" & ".join(tex(c) for c in row) + r" \\" for row in ROWS]
lines += [r"\bottomrule", r"\end{tabularx}", r"\end{table*}"]
(OUT / "tab_frameworks.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("wrote", OUT / "tab_frameworks.tex")
