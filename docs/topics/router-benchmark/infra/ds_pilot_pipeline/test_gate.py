import importlib.util, glob, pathlib
spec = importlib.util.spec_from_file_location("pg", "precise_gate.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for ch, task in [("rb_ds__jekyll__jekyll-8771__r1", "jekyll__jekyll-8771"), ("rb_ds__fmtlib__fmt-3158__r2", "fmtlib__fmt-3158"), ("rb_ds__caddyserver__caddy-6051__r1", "caddyserver__caddy-6051"), ("rb_ds__sharkdp__bat-2650__r1", "sharkdp__bat-2650")]:
    fs = sorted(glob.glob(f"/home/coder/chains/{ch}/home/.claude/projects/*/*.jsonl"))
    g = m.scan(pathlib.Path(fs[-1]), task, "/home/coder/repo"); g.pop("final", None)
    print(task, g["verdict"], g["reasons"][:2])
