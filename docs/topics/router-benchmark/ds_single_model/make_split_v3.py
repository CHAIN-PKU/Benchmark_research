"""DS 单模型研究：剩余 270 道题的分组（v3，2026-11-14，跑之前冻结）。

输入：claw 题库 full-test.jsonl（350 道，sha256 前缀 13914c80）与已用的 80 道（split v2）。
规则（种子 20261114，只看仓库名和题号，不看任何模型结果）：
  1. 270 道未用题按仓库分组。
  2. 盲测 B 层（新仓库）：在「提炼组里从没出现过的仓库」中按种子随机抽一半仓库，整仓库进 B 层。
  3. 盲测 A 层（老仓库的新提交）：其余仓库的题，每个仓库按种子随机抽约 30%（向下取整，至少 0）进 A 层。
  4. 剩下的进提炼组扩充（mining_ext）。
输出：split_ds_single_v3_20261114.csv（instance_id, repo, language, group, layer）及其 sha256。
"""
import csv, hashlib, json, random, sys, collections, pathlib

pool_path, v2_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
rng = random.Random(20261114)
rows = [json.loads(l) for l in open(pool_path)]
used = {r["instance_id"] for r in csv.DictReader(open(v2_path))}
mining_repos = {r["repo"] for r in csv.DictReader(open(v2_path))}
rest = [r for r in rows if r["instance_id"] not in used]
by_repo = collections.defaultdict(list)
for r in rest:
    by_repo[r["repo"]].append(r)
for v in by_repo.values():
    v.sort(key=lambda r: r["instance_id"])

new_repos = sorted(r for r in by_repo if r not in mining_repos)
rng.shuffle(new_repos)
blind_b_repos = set(new_repos[: len(new_repos) // 2])

out = []
for repo in sorted(by_repo):
    tasks = by_repo[repo]
    if repo in blind_b_repos:
        out += [(t, "blind", "B_new_repo") for t in tasks]
        continue
    idx = list(range(len(tasks)))
    rng.shuffle(idx)
    k = int(len(tasks) * 0.3)
    hold = set(idx[:k])
    for i, t in enumerate(tasks):
        out.append((t, "blind", "A_same_repo") if i in hold else (t, "mining_ext", "-"))

with open(out_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["instance_id", "repo", "language", "group", "layer"])
    for t, g, l in sorted(out, key=lambda x: x[0]["instance_id"]):
        w.writerow([t["instance_id"], t["repo"], t.get("language", ""), g, l])
h = hashlib.sha256(pathlib.Path(out_path).read_bytes()).hexdigest()
pathlib.Path(out_path).with_suffix(".sha256").write_text(f"{h}  {pathlib.Path(out_path).name}\n")
c = collections.Counter((g, l) for _, g, l in out)
print(len(out), dict(c), "blind_B_repos", len(blind_b_repos), "sha256", h)
