"""图 1：benchmark 搭建八步流程（内容来自 docs/roadmap.md）。"""
from style import ICML_FULL, STAGE, arrow, canvas, card, save

fig, ax = canvas(ICML_FULL, 2.75)          # 100 x ~40.7 单位
W, H = 16.4, 12.4
COLS = [0.5, 18.4, 36.3, 54.2]
ROW1, ROW2 = 22.0, 2.5

steps = [
    ("design", "Scope", ["Which skill, and why", "existing sets miss it"]),
    ("design", "Task Sources", ["Real commits, issues,", "data; never synthetic"]),
    ("build", "Freeze Env", ["Task + pinned deps", "in a container"]),
    ("build", "Grader", ["Tests / exact match", "first; judge + schema"]),
    ("validate", "Calibrate", ["Cheap & strong LLMs", "≥4 runs → pass rate"]),
    ("validate", "Leak Audit", ["Symptom-only prompt", "BenchJack V1–V8"]),
    ("release", "Evaluate", ["Same turns, time, env", "env failures excluded"]),
    ("release", "Analyze", ["Read every failure,", "write the paper"]),
]
pos = [(COLS[0], ROW1), (COLS[1], ROW1), (COLS[2], ROW1), (COLS[3], ROW1),
       (COLS[3], ROW2), (COLS[2], ROW2), (COLS[1], ROW2), (COLS[0], ROW2)]

for i, ((stage, title, lines), (x, y)) in enumerate(zip(steps, pos), start=1):
    card(ax, x, y, W, H, stage, title, lines, num=i)

# 主流程：第一行向右，拐下来，第二行向左
mid1, mid2 = ROW1 + H / 2, ROW2 + H / 2
for a, b in [(0, 1), (1, 2), (2, 3)]:
    arrow(ax, (pos[a][0] + W, mid1), (pos[b][0], mid1))
arrow(ax, (COLS[3] + W - 3.5, ROW1), (COLS[3] + W - 3.5, ROW2 + H))
for a, b in [(4, 5), (5, 6), (6, 7)]:
    arrow(ax, (pos[a][0], mid2), (pos[b][0] + W, mid2))

# 返工回路（红色虚线，标签带白底压在线上）
red = STAGE["alert"][0]
dash = (0, (3, 2))
arrow(ax, (COLS[3] + 4, ROW2 + H), (COLS[2] + W - 4, ROW1), color=red, ls=dash, lw=0.9,
      rad=-0.3, label="too easy / hard: rebuild", label_color=red, label_size=5.6)
arrow(ax, (COLS[2] + 4, ROW2 + H), (COLS[1] + W - 4, ROW1), color=red, ls=dash, lw=0.9,
      rad=-0.3, label="leak found: re-source", label_color=red, label_size=5.6)

ax.text(0.5, 37.6, "Benchmark Construction Pipeline", ha="left", va="center", fontsize=7.6,
        fontweight="bold", color="#1F2A30")

# 右侧：三条辅线，各自标明接在哪一步
ax.plot([72.4, 72.4], [2.5, 34.4], color="#C9CED2", lw=0.7, ls=(0, (2, 2)))
ax.text(86.4, 37.6, "Connected Research Lines", ha="center", va="center", fontsize=7.6,
        fontweight="bold", color=STAGE["side"][0])
side = [
    ("Post-training", ["Graders become", "verifiable RL rewards"], "step 4"),
    ("Data Attribution", ["Which training data", "explains each failure"], "step 7"),
    ("Data Synthesis", ["Target weak skills;", "train-only, never test"], "step 5"),
]
SH = 9.6
for k, (title, lines, chip) in enumerate(side):
    card(ax, 74.4, ROW2 + 2 * (SH + 1.3) - k * (SH + 1.3), 25.1, SH, "side", title, lines,
         chip=f"← {chip}")

save(fig, "fig_pipeline")
