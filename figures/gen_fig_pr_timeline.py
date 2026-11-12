"""图 3：2026-11-12 当天 10 个 PR 从创建到合并的时间线（真实数据，来自 gh pr list，时间为北京时间）。"""
import datetime as dt

import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from style import ICML_FULL, STAGE, save

TZ = dt.timezone(dt.timedelta(hours=8))
# number, created (UTC), merged (UTC), developer, short title
PRS = [
    (1, "13:25:18", "14:13:08", "Claude", "Contributing guide"),
    (2, "13:28:56", "14:12:34", "DSH", "DSH plugin skill"),
    (3, "13:34:20", "14:12:12", "Claude", "Local CI"),
    (4, "13:53:08", "14:12:47", "Claude", "Research skills"),
    (5, "13:53:23", "14:12:41", "DSH", "Framework survey"),
    (6, "14:00:38", "14:12:53", "Claude", "Research wiki"),
    (7, "14:08:53", "14:12:59", "Claude", "Roadmap + shortlist"),
    (8, "14:42:45", "15:11:45", "Claude", "README contents"),
    (9, "15:12:32", "15:14:52", "Claude", "BenchJack bash 3.2 fix"),
    (10, "15:35:06", "15:38:56", "DSH", "Dev runbook"),
]
DEV_COLOR = {"Claude": STAGE["build"][0], "DSH": STAGE["side"][0]}


def t(hms):
    return dt.datetime.fromisoformat(f"2026-11-12T{hms}+00:00").astimezone(TZ)


fig, ax = plt.subplots(figsize=(ICML_FULL, 2.45))
for row, (n, c, m, dev, title) in enumerate(PRS):
    start, end = t(c), t(m)
    ax.barh(row, mdates.date2num(end) - mdates.date2num(start), left=mdates.date2num(start),
            height=0.55, color=DEV_COLOR[dev], alpha=0.85, edgecolor="white", linewidth=0.5)
    ax.plot(mdates.date2num(end), row, marker="o", ms=3.2, color="#1F2A30", zorder=3)
    mins = (end - start).total_seconds() / 60
    ax.text(mdates.date2num(end) + 0.0012, row, f"#{n} {title}  ({mins:.0f} min)",
            va="center", ha="left", fontsize=6.2, color="#3D474D")

perm = dt.datetime(2026, 11, 12, 22, 11, tzinfo=TZ)
ax.axvline(mdates.date2num(perm), color=STAGE["alert"][0], lw=0.9, ls=(0, (3, 2)))
ax.text(mdates.date2num(perm) - 0.0012, -0.95, "merge permission granted 22:11",
        ha="right", va="center", fontsize=6.0, color=STAGE["alert"][0], style="italic")

ax.set_yticks([])
ax.invert_yaxis()
ax.set_ylim(len(PRS) - 0.4, -1.5)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=TZ))
ax.xaxis.set_major_locator(mdates.MinuteLocator(byminute=[0, 30], tz=TZ))
ax.set_xlim(mdates.date2num(dt.datetime(2026, 11, 12, 21, 20, tzinfo=TZ)),
            mdates.date2num(dt.datetime(2026, 11, 13, 0, 5, tzinfo=TZ)))
ax.set_xlabel("Beijing time, 2026-11-12  (bar: PR open → merged)")
ax.spines["left"].set_visible(False)
ax.grid(axis="y", visible=False)
handles = [plt.Rectangle((0, 0), 1, 1, color=c, alpha=0.85) for c in DEV_COLOR.values()]
ax.legend(handles, [f"built by {d}" for d in DEV_COLOR], loc="upper right", ncol=1, fontsize=6.5)
ax.tick_params(axis="x", labelsize=7)
ax.xaxis.label.set_size(7.5)

save(fig, "fig_pr_timeline")
