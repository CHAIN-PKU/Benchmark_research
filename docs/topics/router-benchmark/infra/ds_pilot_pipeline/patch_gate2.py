import pathlib
p = pathlib.Path("precise_gate.py"); t = p.read_text()
a = "    info = DL[task]; repo, base = info[\"repo\"], info[\"base\"]\n"
assert t.count(a) == 1
t = t.replace(a, "    info = DL[task] if task in DL else _rb_distinct(task); repo, base = info[\"repo\"], info[\"base\"]\n")
helper = '''

# rb 11-14：老 distinct_lines.json 只覆盖老流水线跑过的题；新题按 prep_distinct.py 同样的规则现算
# （基线文件内容取自本次运行工作区里的 base 提交），结果缓存到本目录 distinct_lines_rb.json，不改老文件。
_RB_DL_PATH = pathlib.Path(__file__).resolve().parent / "distinct_lines_rb.json"
def _rb_distinct(task):
    cache = json.loads(_RB_DL_PATH.read_text()) if _RB_DL_PATH.exists() else {}
    if task in cache:
        return cache[task]
    r = rows[task]
    files = re.findall(r"^diff --git a/(\\S+) b/", r["patch"], re.M)
    base_lines, missing = set(), []
    for f in files:
        q = subprocess.run(["git", "-C", str(_WS_GIT), "show", f"{r['base_commit']}:{f}"], capture_output=True, text=True, errors="replace")
        if q.returncode: missing.append(f)
        base_lines |= {norm(x) for x in q.stdout.splitlines()}
    ps = norm(r.get("problem_statement", ""))
    GEN = re.compile(r"(^|/)(parser|lexer)\\.[ch]$|generated_parser\\.y\\.go$|\\.pb\\.go$|\\.prebuilt$")
    parts = re.split(r"(?m)^diff --git a/(\\S+) b/\\S+\\n", r["patch"])
    keep = "\\n".join(parts[i + 1] for i in range(1, len(parts), 2) if not GEN.search(parts[i]))
    g = {norm(x[1:]) for x in keep.splitlines() if x.startswith("+") and not x.startswith("+++")}
    dist = sorted(x for x in g if len(x) >= 25 and x not in base_lines and x not in ps)
    info = {"repo": r["repo"], "base": r["base_commit"], "files": files, "new_files": missing, "distinct": dist,
            "source": "rb _rb_distinct (prep_distinct.py 同规则，基线取自运行工作区)"}
    cache[task] = info
    _RB_DL_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return info
'''
a2 = "def key(s): return"
assert t.count(a2) == 1
t = t.replace(a2, helper.lstrip("\n") + "\n" + a2)
p.write_text(t)
print("patched")
