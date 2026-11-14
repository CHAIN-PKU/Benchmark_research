"""DeepSWE 抽题规则（2026-11-15 写死，跑 DS 正式批之前冻结）。

只用题目元数据，不看任何模型结果（试跑过的 3 道也按同一规则对待，不特殊处理）：
  1. 输入：deep-swe 官方仓库 tasks/*/task.toml（记录仓库 commit）。
  2. 按 language 分层：总数 N 按比例分配（最大余数法），每种语言至少 min(3, 该语言题数)。
  3. 每层按 task_id 排序后用种子 20261115 随机抽；再整体打乱，前 20% 为 blind（盲测组，预测冻结前不跑），其余 mining。
  4. 输出 csv（task_id, language, category, repository_url, base_commit, docker_image, group）及 sha256。
用法：python3 make_deepswe_sample.py <deep-swe/tasks 目录> <N> <out.csv>
"""
import collections, csv, hashlib, json, pathlib, random, re, sys

tasks_dir, N, out_path = pathlib.Path(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
SEED = 20261115
FIELDS = ("task_id", "language", "category", "repository_url", "base_commit_hash", "docker_image")


def meta(toml):
    t = toml.read_text()
    return {k: (re.search(rf'^{k}\s*=\s*"([^"]*)"', t, re.M) or [None, ""])[1] for k in FIELDS}


rows = [meta(p) for p in sorted(tasks_dir.glob("*/task.toml"))]
by = collections.defaultdict(list)
for r in rows:
    by[r["language"]].append(r)
for v in by.values():
    v.sort(key=lambda r: r["task_id"])
floor = {k: min(3, len(v)) for k, v in by.items()}
rest = N - sum(floor.values())
raw = {k: rest * len(v) / len(rows) for k, v in by.items()}
alloc = {k: floor[k] + int(raw[k]) for k in by}
for k in sorted(by, key=lambda k: -(raw[k] - int(raw[k])))[:N - sum(alloc.values())]:
    alloc[k] += 1
alloc = {k: min(alloc[k], len(by[k])) for k in by}

rng = random.Random(SEED)
picked = []
for k in sorted(by):
    picked += rng.sample(by[k], alloc[k])
picked.sort(key=lambda r: r["task_id"])
order = picked[:]
rng.shuffle(order)
n_blind = round(len(order) * 0.2)
group = {r["task_id"]: ("blind" if i < n_blind else "mining") for i, r in enumerate(order)}

with open(out_path, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["task_id", "language", "category", "repository_url", "base_commit", "docker_image", "group"])
    for r in picked:
        w.writerow([r["task_id"], r["language"], r["category"], r["repository_url"], r["base_commit_hash"],
                    r["docker_image"], group[r["task_id"]]])
h = hashlib.sha256(pathlib.Path(out_path).read_bytes()).hexdigest()
pathlib.Path(out_path + ".sha256").write_text(f"{h}  {pathlib.Path(out_path).name}\n")
print(json.dumps({"pool": len(rows), "by_lang": {k: len(v) for k, v in by.items()}, "alloc": alloc,
                  "picked": len(picked), "blind": n_blind, "sha256": h}, ensure_ascii=False))
