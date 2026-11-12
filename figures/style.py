"""论文图的公共样式：字体、配色、尺寸、导出。

配色与 academic-plotting skill 的 "Ocean Dusk" 一致（色盲友好）；
示意图的卡片用「深色描边 + 同色浅底」，参考 SWE-bench / BenchJack 论文里的画法。
"""
import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = pathlib.Path(__file__).resolve().parent / "out"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "DejaVu Serif"],
    "font.size": 9, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.labelsize": 9, "legend.fontsize": 8, "legend.frameon": False,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.18, "grid.linestyle": "-",
    "lines.linewidth": 1.6, "lines.markersize": 4,
    "pdf.fonttype": 42, "ps.fonttype": 42,  # 嵌入 TrueType，期刊排版不出错
    "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
})

COLORS = ["#264653", "#2A9D8F", "#E9C46A", "#F4A261", "#E76F51", "#0072B2", "#56B4E9", "#8C8C8C"]
OUR_COLOR = "#E76F51"
BASELINE_COLOR = "#B0BEC5"

# 示意图的阶段色：(描边, 浅底)
STAGE = {
    "design": ("#2A9D8F", "#E6F4F2"),
    "build": ("#0072B2", "#E5F0F8"),
    "validate": ("#7B5EA7", "#EFEAF6"),
    "release": ("#4F7D3A", "#EBF3E6"),
    "side": ("#C4703A", "#FBEFE6"),
    "neutral": ("#5F6B73", "#F2F4F5"),
    "alert": ("#C0392B", "#FBEAE8"),
}

ICML_SINGLE, ICML_FULL = 3.25, 6.75  # 英寸


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf")
    fig.savefig(OUT / f"{name}.png", dpi=300)
    plt.close(fig)
    print("wrote", OUT / f"{name}.pdf", "and .png")


def card(ax, x, y, w, h, stage, title, lines=(), num=None, chip=None,
          title_size=6.8, body_size=6.0, line_gap=2.6):
    """圆角卡片：编号圆圈 + 粗体标题（+ 右上角小标签）+ 若干行说明。
    坐标是数据坐标，左下角为 (x, y)；画布 1 个单位约 4.9pt（6.75 英寸宽、100 单位）。"""
    edge, face = STAGE[stage]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.0",
                                linewidth=1.1, edgecolor=edge, facecolor=face, zorder=2))
    ty = y + h - 2.4
    tx = x + 1.1
    if num is not None:
        ax.add_patch(plt.Circle((x + 2.3, ty), 1.35, facecolor="white", edgecolor=edge,
                                linewidth=1.0, zorder=3))
        ax.text(x + 2.3, ty, str(num), ha="center", va="center", fontsize=6.3,
                fontweight="bold", color=edge, zorder=4)
        tx = x + 4.2
    ax.text(tx, ty, title, ha="left", va="center", fontsize=title_size,
            fontweight="bold", color="#1F2A30", zorder=4)
    if chip:
        ax.text(x + w - 1.0, ty, chip, ha="right", va="center", fontsize=5.4,
                style="italic", color=edge, zorder=4)
    for i, line in enumerate(lines):
        ax.text(x + 1.3, y + h - 5.6 - i * line_gap, line, ha="left", va="center",
                fontsize=body_size, color="#3D474D", zorder=4)


def arrow(ax, p, q, color="#2B2B2B", style="-|>", lw=1.2, ls="-", rad=0.0, label=None,
          label_xy=None, label_color="#D9822B", label_size=7.5, mutation=9):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=mutation, lw=lw,
                                 color=color, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}", zorder=1,
                                 shrinkA=0, shrinkB=0))
    if label:
        lx, ly = label_xy or ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
        ax.text(lx, ly, label, ha="center", va="center", fontsize=label_size,
                fontweight="bold", color=label_color, zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none"))


def canvas(width_in, height_in, xmax=100, ymax=None):
    ymax = ymax or xmax * height_in / width_in
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax
