#!/usr/bin/env python3
"""DS 单模型研究：试跑运行器（2026-11-13，Claude；DSH 20:37 放行）。

在复制版 claw_iso_rb（老 claw_iso 的拷贝，只改路径和 500 轮 / 10800 秒）之上：
  * 不用 LLM 评委：只按官方 swebench harness（独立 venv，4.1.0）的 resolved 判定过 / 不过。
  * 每题先做自检：gold 补丁必须 resolved；「空改动」（只加一个无关文件）必须 unresolved。
  * 每次运行一个独立链目录、独立 run_id（含补丁哈希），记录轮数 / 用时 / 截断 / 花费。
  * 不移动、不覆盖任何老记录；结果只写进本目录 runs/。
用法：
  ds_pilot.py check <task>            gold / 空改动自检
  ds_pilot.py run <task> <rep>        DS 跑一次
"""
import hashlib, json, os, pathlib, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import claw_iso_rb as CI  # noqa: E402
import claw_batch as CB  # noqa: E402  （claw_iso_rb 已把 scratchpad 加进 sys.path）
import keyring  # noqa: E402

MODEL = "deepseek/deepseek-v4.1-flash"
PY = "/home/ubuntu/benchmark_router_paper/claude_eval/venv/bin/python"
RUNS = HERE / "runs"
EVAL = HERE / "evalwork"
NOOP = ("diff --git a/RB_NOOP.txt b/RB_NOOP.txt\nnew file mode 100644\nindex 0000000..e69de29\n"
        "--- /dev/null\n+++ b/RB_NOOP.txt\n@@ -0,0 +1 @@\n+noop\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def harness(task, patch, label, outdir):
    """官方 harness 评一份补丁，返回逐测试结果 + resolved。"""
    outdir.mkdir(parents=True, exist_ok=True)
    r = CI.ROWS[task]
    ds = outdir / "dataset.json"
    ds.write_text(json.dumps([CI._ds_row(r)], ensure_ascii=False))
    pred = outdir / "pred.jsonl"
    pred.write_text(json.dumps({"instance_id": task, "model_patch": patch, "model_name_or_path": label}, ensure_ascii=False) + "\n")
    pred2, dropped = CB.strip_test_collisions(str(pred), str(ds))
    h = hashlib.sha1(pathlib.Path(pred2).read_bytes()).hexdigest()[:10]
    run_id = f"rb_{label}_{task[:40]}_{h}"
    EVAL.mkdir(exist_ok=True)
    lk = CB.docker_lock()
    try:
        # 评测前先拉镜像并记 digest（swebench 评完会自己删实例镜像，事后取不到）
        img = f"swebench/sweb.eval.x86_64.{task.replace('__', '_1776_')}:latest"
        CI.sh(f"docker pull -q {img}", timeout=3600)
        dg = CI.sh(f"docker image inspect --format '{{{{json .RepoDigests}}}}' {img}").stdout.strip()
        p = CI.sh(f"{PY} -m swebench.harness.run_evaluation --dataset_name '{ds}' --predictions_path '{pred2}' "
                  f"--max_workers 1 --run_id {run_id} --cache_level env --timeout 3600", cwd=str(EVAL), timeout=7200)
        (outdir / "harness_stdout.txt").write_text((p.stdout or "") + "\n--- stderr ---\n" + (p.stderr or ""))
        rps = list(EVAL.glob(f"logs/run_evaluation/{run_id}/*/{task}/report.json"))
        if not rps:
            return {"error": f"no report.json (rc={p.returncode})", "run_id": run_id}
        d = json.loads(rps[0].read_text())
        body = d[list(d)[0]]
        ts = body.get("tests_status") or {}
        res = {"image": img, "image_repo_digests": dg or "未取到",
               "resolved": bool(body.get("resolved")), "patch_applied": bool(body.get("patch_successfully_applied")),
               "f2p_success": sorted(ts.get("FAIL_TO_PASS", {}).get("success") or []),
               "f2p_failure": sorted(ts.get("FAIL_TO_PASS", {}).get("failure") or []),
               "p2p_failure": sorted(ts.get("PASS_TO_PASS", {}).get("failure") or []),
               "p2p_success_n": len(ts.get("PASS_TO_PASS", {}).get("success") or []),
               "test_collision_dropped": dropped, "run_id": run_id, "report_path": str(rps[0])}
        for f in rps[0].parent.iterdir():   # 留证据：report / test_output / run_instance.log
            if f.is_file() and f.stat().st_size < 50_000_000:
                (outdir / f.name).write_bytes(f.read_bytes())
        return res
    finally:
        CB.clean_docker(CI.log)
        lk.close()


def check(task):
    od = RUNS / task / "selfcheck"
    r = CI.ROWS[task]
    g = harness(task, r["patch"], "gold", od / "gold")
    n = harness(task, NOOP, "noop", od / "noop")
    ok = g.get("resolved") is True and n.get("resolved") is False and not g.get("error") and not n.get("error")
    rec = {"task": task, "gold": g, "noop": n, "selfcheck_ok": ok, "at": time.strftime("%F %T")}
    (od / "selfcheck.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    CI.log(f"[rb check] {task} ok={ok} gold={g.get('resolved')} noop={n.get('resolved')}")
    return rec


def run(task, rep):
    sc = RUNS / task / "selfcheck/selfcheck.json"
    if not sc.exists() or not json.loads(sc.read_text())["selfcheck_ok"]:
        raise SystemExit(f"{task} 自检没过，不跑")
    od = RUNS / task / f"ds_r{rep}"
    if (od / "record.json").exists():
        raise SystemExit(f"{od} 已有结果")
    od.mkdir(parents=True, exist_ok=True)
    if CI.disk_pct() >= 93:
        raise SystemExit("磁盘 >= 93%")
    chain = f"rb_ds__{task}__r{rep}"
    if CI.SB.chain_dir(chain).exists():
        raise SystemExit(f"链目录 {chain} 已存在")
    info, ws, meta = CI.make_chain(chain, task)
    r = CI.ROWS[task]
    prompt = f"""这个仓库里有一个问题需要你解决。

## 问题描述
{(r.get('problem_statement') or '')[:8000]}

**要求：**
- 直接改产品代码把问题解决掉，不要只改测试
- 只做这个问题要求的改动，不要顺手重构无关代码
- 保持仓库现有的代码风格和结构
"""
    lang = CI.lang_of(task)
    env = CI.SB.agent_env(MODEL, None, CI.PORT[MODEL], keyring.pick_key(), CI.sandbox_extra(lang, task))
    argv = [CI.SB.CLAUDE_BIN, "-p", "--model", MODEL, "--permission-mode", "bypassPermissions", "--effort", CI.EFFORT,
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--max-turns", str(CI.TURNS),
            "--disallowedTools", "WebSearch", "WebFetch", "--output-format", "json", prompt]
    b0 = CI.or_total()

    def guard():
        b = CI.or_total()
        return f"balance ${b:.2f} < {CI.HARD_FLOOR}" if b is not None and b < CI.HARD_FLOOR else None

    CI.log(f"[rb run] {task} r{rep} chain={chain} turns={CI.TURNS} timeout={CI.TIMEOUT}")
    out, err, killed, el = CI.run_in_sandbox(chain, ws, argv, env, CI.TIMEOUT, guard,
                                             conda=task if lang == "python" else None)
    time.sleep(10)
    b1 = CI.or_total()
    return post(task, rep, od, chain, ws, info, out, err, killed, el, b0, b1)


def load_gate():
    """用本目录的 precise_gate 复制版（老版写死了已归档的题库路径）；按文件路径加载，避免被 sys.path 里的老版遮住。"""
    import importlib.util
    spec = importlib.util.spec_from_file_location("precise_gate_rb", HERE / "precise_gate.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def post(task, rep, od, chain, ws, info, out, err, killed, el, b0, b1):
    r = CI.ROWS[task]
    lang = CI.lang_of(task)
    try:
        j = json.loads(out)
    except Exception:
        j = {}
    d = CI.sh(f"git add -A && git diff --cached {r['base_commit']}", cwd=str(ws))
    patch, artifacts = CI.exclude_artifacts(ws, r["base_commit"], d.stdout or "")
    (od / "model_patch.diff").write_text(patch)
    (od / "agent_stdout.json").write_text(out or "")
    (od / "agent_stderr.txt").write_text(err or "")
    sf = CI.SB.project_dir(chain) / f"{j.get('session_id')}.jsonl"
    if not sf.exists():
        c = sorted(CI.SB.project_dir(chain).glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
        sf = c[-1] if c else None
    PG = load_gate()
    g = PG.scan(sf, task, "/home/coder/repo") if sf else {"verdict": "uncertain", "reasons": ["找不到会话"]}
    g.pop("final", None)
    if sf:
        (od / "session.jsonl").write_bytes(pathlib.Path(sf).read_bytes())
    turns = j.get("num_turns")
    rec = {"task": task, "rep": rep, "model": MODEL, "repo": r["repo"], "lang": lang,
           "max_turns": CI.TURNS, "timeout_s": CI.TIMEOUT, "turns": turns, "elapsed_s": el, "killed": killed,
           "truncated": bool(killed == "timeout" or (turns or 0) >= CI.TURNS or j.get("subtype") == "error_max_turns"),
           "subtype": j.get("subtype"), "stop_reason": j.get("stop_reason"), "is_error": j.get("is_error"),
           "usage": j.get("usage") or {}, "cost_cc_reported": j.get("total_cost_usd"),
           "or_balance_before_after": [b0, b1], "or_spend_usd": (round(b0 - b1, 6) if b0 is not None and b1 is not None else None),
           "patch_chars": len(patch), "patch_sha256": hashlib.sha256(patch.encode()).hexdigest(),
           "artifacts_excluded": artifacts, "leak_gate": g, "chain": chain, "shim_port": CI.PORT[MODEL],
           "claude_version": info.get("claude_version"), "judge": "none (pure tests)", "at": time.strftime("%F %T")}
    if killed and killed != "timeout":
        rec["unscored_reason"] = f"budget kill: {killed}"
    elif g.get("verdict") == "contaminated":
        rec["unscored_reason"] = "leak gate: contaminated"
    elif not patch.strip():
        rec.update({"resolved": False, "zero_patch": True})
    else:
        h = harness(task, patch, f"ds{rep}", od / "eval")
        rec["eval"] = h
        if h.get("error"):
            rec["unscored_reason"] = h["error"]
        else:
            rec["resolved"] = h["resolved"]
    (od / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    CI.sh(f"sudo -n rm -rf '{CI.SB.chain_dir(chain)}/home/.rustup' '{CI.SB.chain_dir(chain)}/home/.cargo/registry' "
          f"'{CI.SB.chain_dir(chain)}/home/go' '{ws}/node_modules' '{ws}/vendor' '{CI.SB.chain_dir(chain)}/home/.bundle-gems'")
    CI.log(f"[rb run] ★ {task} r{rep} resolved={rec.get('resolved')} turns={turns} el={el}s or=${rec['or_spend_usd']} "
           f"trunc={rec['truncated']} gate={g.get('verdict')} {rec.get('unscored_reason', '')}")
    return rec


def finish(task, rep):
    """agent 已跑完、后处理崩了：从留下的 stdout 和链目录补做闸门 + 评测（不重跑 agent）。"""
    od = RUNS / task / f"ds_r{rep}"
    if (od / "record.json").exists():
        raise SystemExit(f"{od} 已有结果")
    chain = f"rb_ds__{task}__r{rep}"
    out = (od / "agent_stdout.json").read_text()
    err = (od / "agent_stderr.txt").read_text()
    try:
        el = round(json.loads(out).get("duration_ms", 0) / 1000, 1)
    except Exception:
        el = None
    rec = post(task, rep, od, chain, CI.SB.chain_dir(chain) / "ws", {}, out, err, None, el, None, None)
    rec["finished_post_hoc"] = "agent 正常跑完；后处理第一次因闸门脚本路径崩溃，补做闸门+评测；or 余额差缺失，看 cost_cc_reported"
    (od / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "check":
        print(json.dumps(check(a[1]), ensure_ascii=False)[:1500])
    elif a[0] == "run":
        print(json.dumps(run(a[1], int(a[2])), ensure_ascii=False)[:1500])
    elif a[0] == "finish":
        print(json.dumps(finish(a[1], int(a[2])), ensure_ascii=False)[:1500])
