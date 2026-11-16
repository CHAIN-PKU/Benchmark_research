import pathlib, re
p = pathlib.Path("precise_gate.py"); t = p.read_text()
a = '    g = str(H / "repos" / (repo.replace("/", "_") + ".git"))\n'
assert t.count(a) == 1
t = t.replace(a, '    g = _WS_GIT if _WS_GIT and os.path.isdir(_WS_GIT) else str(H / "repos" / (repo.replace("/", "_") + ".git"))\n')
a = "@functools.lru_cache(maxsize=None)\ndef ref_state(repo, base, tok):\n"
assert t.count(a) == 1
t = t.replace(a, "_WS_GIT = None   # rb 11-13：老的上游镜像目录已归档；改查本次运行的工作区（只留了 base 及以前的历史）\n\n\n" + a)
a = "def scan(f, task, wd_hint):\n"
assert t.count(a) == 1
t = t.replace(a, a + "    global _WS_GIT\n    _m = re.search(r\"(/home/coder/chains/[^/]+)/\", str(f))\n    _WS_GIT = (_m.group(1) + \"/ws\") if _m else None\n")
p.write_text("# rb 11-13 23:3x：ref_state 改查本次运行的工作区（修 jekyll-8771 误判：过去的提交被当成未来）\n" + t)
print("patched")
