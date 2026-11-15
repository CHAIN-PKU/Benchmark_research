"""把 DS 会话记录压成「过程摘要」：每步工具调用（名字+关键参数）、是否跑过测试、最终自述。
用法：python3 make_traj.py <runs_dir> <tasks.json> <out_dir>"""
import json, pathlib, re, sys
runs, tasks, out = pathlib.Path(sys.argv[1]), json.load(open(sys.argv[2])), pathlib.Path(sys.argv[3])
TEST = re.compile(r"(pytest|go test|npm (run )?test|yarn test|cargo test|bundle exec|rspec|phpunit|mvn .*test|gradle.*test|ctest|make test|runtests|tox|jest|vitest|mocha)", re.I)
for t in tasks:
    for i in (1, 2):
        f = runs / t / f"dsh_r{i}" / "session.jsonl"
        if not f.exists():
            continue
        steps, last_text, ran_test = [], "", False
        for line in open(f, errors="ignore"):
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get("type") != "assistant":
                continue
            for c in (d.get("message") or {}).get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "tool_use":
                    inp = c.get("input") or {}
                    if c["name"] == "Bash":
                        arg = inp.get("command", "")
                        ran_test |= bool(TEST.search(arg))
                    else:
                        arg = inp.get("file_path") or inp.get("pattern") or inp.get("path") or json.dumps(inp, ensure_ascii=False)
                    steps.append(f"{c['name']}: {str(arg)[:160]}".replace("\n", " "))
                elif c.get("type") == "text" and c.get("text", "").strip():
                    last_text = c["text"]
        d = out / t
        d.mkdir(parents=True, exist_ok=True)
        (d / f"run{i}_trajectory.md").write_text(
            f"# run{i} 过程摘要\n- 工具调用 {len(steps)} 步；跑过测试命令：{'是' if ran_test else '否'}\n\n## 步骤\n"
            + "\n".join(f"{k+1}. {s}" for k, s in enumerate(steps))
            + f"\n\n## 最后一段自述（截断）\n{last_text[-2500:]}\n")
print("done")
