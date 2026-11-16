"""汇总 runs/ 下所有 DS 记录：每题两次结果、轮数、用时、成本（按用量折算为准）、闸门。"""
import json, glob, csv, sys
rows = []
for f in sorted(glob.glob("runs/*/ds_r*/record.json")):
    d = json.load(open(f)); e = d.get("eval", {}) or {}
    import os
    bfp = f.rsplit("/", 1)[0] + "/BACKFILL.json"
    bf = json.load(open(bfp)) if os.path.exists(bfp) else {}
    rows.append({"task": d["task"], "rep": d["rep"], "resolved": d.get("resolved"), "turns": d.get("turns"),
                 "elapsed_s": d.get("elapsed_s"), "truncated": d.get("truncated"),
                 "cost_token_est": d.get("cost_token_est_usd") if d.get("cost_token_est_usd") is not None else bf.get("cost_token_est_usd"), "or_delta": d.get("or_spend_usd"),
                 "gate": d["leak_gate"].get("verdict"), "f2p_fail": "|".join(e.get("f2p_failure") or []),
                 "p2p_fail_n": len(e.get("p2p_failure") or []), "digest": "y" if "sha256" in str(e.get("image_repo_digests")) else ("backfilled" if bf.get("image_digest_backfilled") else "n"),
                 "post_hoc": "y" if d.get("finished_post_hoc") or d.get("reevaluated") or d.get("regated") else "",
                 "unscored": d.get("unscored_reason", "")})
w = csv.DictWriter(open("summary_runs.csv", "w"), fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
by = {}
for r in rows: by.setdefault(r["task"], []).append(r["resolved"])
both = sum(1 for v in by.values() if len(v) == 2)
print("records", len(rows), "tasks", len(by), "tasks_with_2", both,
      "pass2", sum(1 for v in by.values() if v == [True, True]), "fail2", sum(1 for v in by.values() if v == [False, False]),
      "flip", sum(1 for v in by.values() if len(v) == 2 and v[0] != v[1]), "unscored", sum(1 for r in rows if r["resolved"] is None))
