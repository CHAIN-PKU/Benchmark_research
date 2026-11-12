"""图 4：结果图的版式示范——(a) pass@k 曲线带误差带，(b) 排行榜横条图。
注意：这是示意数据（由公式生成），不是实验结果；图内也有标注。等有真实结果后替换 DATA。"""
import matplotlib.pyplot as plt
import numpy as np

from style import BASELINE_COLOR, COLORS, ICML_FULL, OUR_COLOR, save

# 示意数据：每个模型的单次通过率 p，pass@k = 1 - (1 - p)^k
MODELS = {"Cheap LLM": 0.08, "Mid LLM": 0.15, "Strong LLM": 0.24, "Strong + tools": 0.31}
HIGHLIGHT = "Strong + tools"
k = np.arange(1, 17)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(ICML_FULL, 2.3), gridspec_kw={"width_ratios": [1.15, 1]})
markers = ["o", "s", "^", "D"]
for i, (name, p) in enumerate(MODELS.items()):
    mean = 1 - (1 - p) ** k
    band = 0.6 * np.sqrt(mean * (1 - mean) / 30)          # 假设每点 30 题时的二项标准误
    color = OUR_COLOR if name == HIGHLIGHT else COLORS[i]
    ax1.plot(k, 100 * mean, marker=markers[i], markevery=3, color=color, label=name,
             lw=2.0 if name == HIGHLIGHT else 1.4, zorder=3)
    ax1.fill_between(k, 100 * (mean - band), 100 * (mean + band), color=color, alpha=0.12, lw=0)
ax1.set_xscale("log", base=2)
ax1.set_xticks([1, 2, 4, 8, 16])
ax1.set_xticklabels(["1", "2", "4", "8", "16"])
ax1.set_xlabel("Attempts k")
ax1.set_ylabel("pass@k (%)")
ax1.set_ylim(0, 100)
ax1.set_title("(a) More attempts, diminishing gains", loc="left", fontsize=8)
ax1.legend(loc="upper left", fontsize=6.3)

board = {"Strong + tools": 31.0, "Strong LLM": 24.0, "Mid LLM": 15.0, "Open 70B": 11.0, "Cheap LLM": 8.0}
names = list(board)
colors = [OUR_COLOR if n == HIGHLIGHT else BASELINE_COLOR for n in names]
bars = ax2.barh(np.arange(len(names)), list(board.values()), color=colors, height=0.55,
                edgecolor="white", linewidth=0.5)
ax2.set_yticks(np.arange(len(names)))
ax2.set_yticklabels(names, fontsize=7)
ax2.invert_yaxis()
ax2.set_xlabel("pass@1 (%)")
ax2.set_xlim(0, 40)
ax2.grid(axis="y", visible=False)
for bar, v in zip(bars, board.values()):
    ax2.text(v + 0.6, bar.get_y() + bar.get_height() / 2, f"{v:.1f}", va="center", fontsize=6.5, color="#444")
ax2.set_title("(b) Leaderboard", loc="left", fontsize=8)

fig.text(0.995, -0.02, "Illustrative data generated from a formula — not experimental results.",
         ha="right", va="top", fontsize=6.2, style="italic", color="#C0392B")
fig.tight_layout(w_pad=2.0)
save(fig, "fig_results_demo")
