"""图 2：两个 agent 的开发—审查循环，右侧是 2026-11-12 当天的真实统计（来自 gh pr list）。"""
from style import ICML_FULL, STAGE, arrow, canvas, card, save

fig, ax = canvas(ICML_FULL, 2.35)          # 100 x ~34.8 单位
W, H = 14.2, 10.0
TOP, BOT = 20.5, 3.0
X = [0.5, 17.6, 34.7, 51.8]

top = [("build", "Develop", ["One change,", "one commit"]),
       ("validate", "Local CI", ["Secrets, size, skill,", "syntax, pytest"]),
       ("validate", "Push", ["Pre-push hook", "re-runs CI"]),
       ("design", "Open PR", ["What changed,", "how verified"])]
bot = [("release", "Merge", ["CI green and", "reviewed once"]),
       ("side", "Cross-model Review", ["The other agent:", "must-fix items only"])]

for i, (s, t, l) in enumerate(top):
    card(ax, X[i], TOP, W, H, s, t, l, num=i + 1, body_size=5.8)
card(ax, X[1], BOT, W, H, *bot[0], num=6, body_size=5.8)
card(ax, X[3] - 6, BOT, W + 6, H, *bot[1], num=5, body_size=5.8)

for i in range(3):
    arrow(ax, (X[i] + W, TOP + H / 2), (X[i + 1], TOP + H / 2))
arrow(ax, (X[3] + W / 2, TOP), (X[3] + W / 2, BOT + H))                    # PR -> review
arrow(ax, (X[3] - 6, BOT + H / 2), (X[1] + W, BOT + H / 2))                 # review -> merge
arrow(ax, (X[1], BOT + H / 2), (X[0] + W / 2, TOP), rad=-0.35)              # merge -> next change
ax.text(X[0] + 1.0, BOT + 3.2, "next\nchange", fontsize=5.6, style="italic", color="#5F6B73",
        ha="left", va="center")

red = STAGE["alert"][0]
dash = (0, (3, 2))
arrow(ax, (X[1] + W / 2, TOP + H), (X[0] + W / 2 + 2, TOP + H), color=red, ls=dash, lw=0.9,
      rad=0.55, label="CI red: fix first", label_color=red, label_size=5.6, label_xy=(X[1] - 3.0, 32.4))
arrow(ax, (X[3] - 3.5, BOT + H - 1), (X[0] + W - 1, TOP), color=red, ls=dash, lw=0.9, rad=-0.15,
      label="must-fix found", label_color=red, label_size=5.6, label_xy=(X[2] + 2.5, 15.6))

# 右侧真实统计
ax.plot([69.6, 69.6], [3, 31], color="#C9CED2", lw=0.7, ls=(0, (2, 2)))
ax.text(84.8, 32.6, "One real day (2026-11-12)", ha="center", va="center", fontsize=7.4,
        fontweight="bold", color="#1F2A30")
stats = [("10", "pull requests merged"),
         ("7 / 3", "built by Claude / by DSH,\nreviewed by the other"),
         ("2", "real bugs caught by review\nor acceptance (PR #4, #9)"),
         ("19.5 min", "median open → merge")]
for k, (big, small) in enumerate(stats):
    y = 26.5 - k * 7.0
    ax.text(72.0, y, big, ha="left", va="center", fontsize=9.5, fontweight="bold",
            color=STAGE["build"][0])
    ax.text(84.0, y, small, ha="left", va="center", fontsize=5.8, color="#3D474D", linespacing=1.15)

save(fig, "fig_collab_loop")
