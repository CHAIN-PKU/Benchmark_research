"""SWE-bench Pro 抽题规则（2026-11-14 写死，跑 DS 之前冻结）。

只用题目本身的信息，不看任何模型（包括 DS）的结果：
  1. 输入：官方公开集元数据（jsonl，每行一道题，含 repo / patch / instance_id）
     + 可选的「我们这套评测能用的题号清单」（v2 镜像集合）。
  2. 预先剔除（环境约束，与能力无关）：标准答案修改依赖清单文件的题
     （package.json、go.mod、requirements*.txt、pyproject.toml 等）——断网沙箱里装不了新依赖。
  3. 按仓库分层：总数 N 按各仓库题数比例分配（最大余数法），每个仓库至少 min(3, 该仓库题数) 道。
  4. 每个仓库内按题号排序后，用种子 20261114 随机抽。
  5. 输出 csv（instance_id, repo, n_files_changed, lines_changed, group）及 sha256。
     group：前 80% 为 mining（提炼组），后 20% 为 blind（盲测组，预测冻结前不跑）。
用法：python3 make_pro_sample.py <meta.jsonl> <N> <out.csv> [allowed_ids.txt]
"""
import collections
import csv
import hashlib
import json
import pathlib
import random
import re
import sys

meta_path, N, out_path = sys.argv[1], int(sys.argv[2]), sys.argv[3]
allowed = set(pathlib.Path(sys.argv[4]).read_text().split()) if len(sys.argv) > 4 else None
SEED = 20261114
MANIFEST = re.compile(r"^diff --git a/(\S*(package\.json|package-lock\.json|yarn\.lock|go\.mod|go\.sum|requirements[^ /]*\.txt|"
                      r"pyproject\.toml|setup\.py|setup\.cfg|Pipfile(\.lock)?|poetry\.lock))\s", re.M)

rows = [json.loads(l) for l in open(meta_path)]
if allowed is not None:
    rows = [r for r in rows if r["instance_id"] in allowed]
excluded = [r["instance_id"] for r in rows if MANIFEST.search(r["patch"])]
rows = [r for r in rows if r["instance_id"] not in set(excluded)]

by = collections.defaultdict(list)
for r in rows:
    by[r["repo"]].append(r)
for v in by.values():
    v.sort(key=lambda r: r["instance_id"])

total = len(rows)
floor = {k: min(3, len(v)) for k, v in by.items()}
rest = N - sum(floor.values())
raw = {k: rest * len(v) / total for k, v in by.items()}
alloc = {k: floor[k] + int(raw[k]) for k in by}
left = N - sum(alloc.values())
for k in sorted(by, key=lambda k: -(raw[k] - int(raw[k])))[:left]:
    alloc[k] += 1
alloc = {k: min(alloc[k], len(by[k])) for k in by}

rng = random.Random(SEED)
picked = []
for k in sorted(by):
    picked += rng.sample(by[k], alloc[k])
picked.sort(key=lambda r: r["instance_id"])
order = picked[:]
rng.shuffle(order)
n_blind = round(len(order) * 0.2)
group = {r["instance_id"]: ("blind" if i < n_blind else "mining") for i, r in enumerate(order)}


def stats(p):
    files = re.findall(r"^diff --git a/(\S+) ", p, re.M)
    lines = sum(1 for l in p.splitlines() if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---")))
    return len(files), lines


with open(out_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["instance_id", "repo", "n_files_changed", "lines_changed", "group"])
    for r in picked:
        nf, nl = stats(r["patch"])
        w.writerow([r["instance_id"], r["repo"], nf, nl, group[r["instance_id"]]])
h = hashlib.sha256(pathlib.Path(out_path).read_bytes()).hexdigest()
pathlib.Path(out_path + ".sha256").write_text(f"{h}  {pathlib.Path(out_path).name}\n")
print(json.dumps({"pool": total + len(excluded), "excluded_dep_manifest": len(excluded), "eligible": total, "picked": len(picked),
                  "alloc": alloc, "blind": n_blind, "sha256": h}, ensure_ascii=False))
