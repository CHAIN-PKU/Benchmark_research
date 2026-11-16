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

MODEL = os.environ.get("RB_MODEL", "deepseek/deepseek-v4.1-flash")
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
        for k in range(3):   # 拉镜像重试 3 次、退避 30 秒；仍失败记为基础设施失败，不当成题的问题
            pr = CI.sh(f"docker pull -q {img}", timeout=3600)
            if pr.returncode == 0:
                break
            time.sleep(30)
        else:
            return {"error": f"infra: image pull failed: {(pr.stderr or pr.stdout)[-300:]}", "infra_fail": True, "image": img}
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
    if g.get("infra_fail") or n.get("infra_fail"):   # 基础设施失败：不写 selfcheck.json，下次重做
        (od / f"selfcheck_infra_{time.strftime('%H%M%S')}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        CI.log(f"[rb check] {task} INFRA_FAIL（拉镜像失败），稍后重做")
        raise SystemExit(f"INFRA_FAIL {task}")
    (od / "selfcheck.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    CI.log(f"[rb check] {task} ok={ok} gold={g.get('resolved')} noop={n.get('resolved')}")
    return rec


def run(task, rep):
    sc = RUNS / task / "selfcheck/selfcheck.json"
    if not sc.exists() or not json.loads(sc.read_text())["selfcheck_ok"]:
        raise SystemExit(f"{task} 自检没过，不跑")
    tag = "ds" if os.environ.get("RB_CHANNEL", "openrouter") == "openrouter" else "dsh"   # 新通道单独目录，不和 OpenRouter 结果混
    od = RUNS / task / f"{tag}_r{rep}"
    if (od / "record.json").exists():
        raise SystemExit(f"{od} 已有结果")
    od.mkdir(parents=True, exist_ok=True)
    if CI.disk_pct() >= 93:
        raise SystemExit("磁盘 >= 93%")
    chain = f"rb_{tag}__{task}__r{rep}"
    if CI.SB.chain_dir(chain).exists():
        raise SystemExit(f"链目录 {chain} 已存在")
    info, ws, meta = CI.make_chain(chain, task)
    r = CI.ROWS[task]
    hint_path = pathlib.Path(__file__).resolve().parent / "gap_hints" / f"{task}.md"
    hint = ""
    if hint_path.exists():
        hint = "## 动手前的落差清单（由另一个预测器生成，供你参考）\n" + hint_path.read_text(errors="ignore") + "\n\n"
    prompt = f"""这个仓库里有一个问题需要你解决。

{hint}## 问题描述
{(r.get('problem_statement') or '')[:8000]}

**要求：**
- 直接改产品代码把问题解决掉，不要只改测试
- 只做这个问题要求的改动，不要顺手重构无关代码
- 保持仓库现有的代码风格和结构
"""
    lang = CI.lang_of(task)
    channel = os.environ.get("RB_CHANNEL", "openrouter")   # openrouter（默认，8776 锁 DeepSeek 官方）/ dsh（DSH 账号代理，经反向隧道）
    if channel == "dsh":
        port = int(os.environ.get("RB_PORT", os.environ["RB_DSH_PORT"]))
        env = CI.SB.agent_env(MODEL, None, port, "dsh-proxy-injects-token", CI.sandbox_extra(lang, task))
    else:
        port = CI.PORT.get(MODEL, 0)
        env = CI.SB.agent_env(MODEL, None, port, keyring.pick_key(), CI.sandbox_extra(lang, task))
    if os.environ.get("RB_OAUTH"):
        env["CLAUDE_CODE_OAUTH_TOKEN"] = os.environ["RB_OAUTH"]
        env.pop("ANTHROPIC_API_KEY", None)
    _base = os.environ.get("RB_BASE_URL")
    if _base:
        for k in ("NO_PROXY", "no_proxy"):
            env[k] = (env.get(k, "") + ",172.17.0.1,127.0.0.1").strip(",")
        env["ANTHROPIC_BASE_URL"] = _base
        env["ANTHROPIC_API_KEY"] = os.environ.get("RB_API_KEY", "sk-local")
        env["ANTHROPIC_AUTH_TOKEN"] = os.environ.get("RB_API_KEY", "sk-local")
    argv = [CI.SB.CLAUDE_BIN, "-p", "--model", MODEL, "--permission-mode", "bypassPermissions", "--effort", CI.EFFORT,
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--max-turns", str(CI.TURNS),
            "--disallowedTools", "WebSearch", "WebFetch", "--output-format", "json", prompt]
    b0 = CI.or_total()

    def guard():
        b = CI.or_total()
        return f"balance ${b:.2f} < {CI.HARD_FLOOR}" if b is not None and b < CI.HARD_FLOOR else None

    CI.log(f"[rb run] {task} r{rep} chain={chain} turns={CI.TURNS} timeout={CI.TIMEOUT}")
    # 11-14：OpenRouter 余额熔断只对 OpenRouter 通道有意义；DSH 通道不花 OpenRouter 的钱，不挂熔断
    out, err, killed, el = CI.run_in_sandbox(chain, ws, argv, env, CI.TIMEOUT, guard if channel == "openrouter" else None,
                                             conda=task if lang == "python" else None)
    time.sleep(10)
    b1 = CI.or_total()
    rec = post(task, rep, od, chain, ws, info, out, err, killed, el, b0, b1)
    rec["channel"], rec["channel_port"] = channel, port
    rec["warmup"] = CI.lang_of(task)   # 2026-11-14 DSH：记录用的是哪种预热（java_maven 等）
    # 2026-11-14 DSH：记录环境来源（own / shared_from_<题> / copied_from_image），便于按环境分开统计
    try:
        rec["env_source"] = pathlib.Path(f"/opt/sbx/conda/{task}.source").read_text().strip()
    except OSError:
        rec["env_source"] = None
    if channel != "openrouter":
        rec["cost_status"] = "dsh 账号通道：OpenRouter 余额差无意义，成本按 DSH 账号 token 计价另算"
    rec["hint"] = bool(hint)
    (od / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


def token_est(usage):
    """token 折算成本（老流水线 cost_lib 口径，含缓存折扣）；失败返回 None。"""
    try:
        import cost_lib
        return cost_lib.token_cost(MODEL, usage)
    except Exception as e:  # noqa: BLE001
        return f"error: {e}"


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
           "cost_status": ("or_balance_delta" if (b0 is not None and b1 is not None and b0 - b1 > 0)
                           else "余额差为 0 或缺失：余额接口有延迟/并发，成本看 cost_token_est_usd，不是 0"),
           "cost_token_est_usd": token_est(j.get("usage") or {}),
           "gate_rule": "precise_gate.scan：thr = min(3, 标准答案特征行数)；联网/未来历史/外部文件里命中特征行 >= thr 判 contaminated",
           "gate_script_sha256": sha(HERE / "precise_gate.py"),
           "artifacts_excluded": artifacts, "leak_gate": g, "chain": chain, "shim_port": CI.PORT.get(MODEL),
           "claude_version": info.get("claude_version"), "judge": "none (pure tests)", "at": time.strftime("%F %T")}
    api_err = j.get("is_error") and "API Error" in str(j.get("result") or "")
    if api_err and (turns or 0) <= 1:   # 模型一轮都没跑起来（连不上/鉴权失败等）：环境故障，不是 DS 做错
        rec["unscored_reason"] = f"infra: api error before any work: {str(j.get('result'))[:200]}"
        rec["infra_fail"] = True
    elif killed and killed != "timeout":
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
    # 腾盘：补丁、会话、评测报告都已存进 od；链里只留 ws/.git（重扫闸门要查提交历史）和 home/.claude（会话原件）
    cd = CI.SB.chain_dir(chain)
    CI.sh(f"sudo -n find '{ws}' -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {{}} + ; "
          f"sudo -n find '{cd}/home' -mindepth 1 -maxdepth 1 ! -name .claude -exec rm -rf {{}} + ; sudo -n rm -rf '{cd}/tmp'")
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


def reeval(task, rep):
    """评测环节因环境（如 Docker Hub 限流）没出报告：用保存的补丁重评，不重跑模型；旧记录留作 record.before_reeval.json。"""
    od = RUNS / task / f"ds_r{rep}"
    rec = json.loads((od / "record.json").read_text())
    if rec.get("resolved") is not None:
        raise SystemExit(f"{od} 已有判定 resolved={rec['resolved']}，不重评")
    (od / "record.before_reeval.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    patch = (od / "model_patch.diff").read_text()
    assert hashlib.sha256(patch.encode()).hexdigest() == rec["patch_sha256"], "补丁文件和记录对不上"
    h = harness(task, patch, f"ds{rep}", od / "eval")
    rec["eval"] = h
    rec.pop("unscored_reason", None)
    if h.get("error"):
        rec["unscored_reason"] = h["error"]
    else:
        rec["resolved"] = h["resolved"]
    rec["reevaluated"] = {"at": time.strftime("%F %T"), "why": "第一次评测没出报告（环境原因），用保存的补丁重评，模型没重跑"}
    (od / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    CI.log(f"[rb reeval] ★ {task} r{rep} resolved={rec.get('resolved')} {rec.get('unscored_reason', '')}")
    return rec


def regate(task, rep):
    """闸门脚本修过之后重扫：用本次运行的会话重新判闸门；不再是 contaminated 且没判过分的，补做评测。模型不重跑。"""
    od = RUNS / task / f"ds_r{rep}"
    rec = json.loads((od / "record.json").read_text())
    (od / f"record.before_regate_{time.strftime('%H%M%S')}.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    chain = rec["chain"]
    c = sorted(CI.SB.project_dir(chain).glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
    PG = load_gate()
    g = PG.scan(c[-1], task, "/home/coder/repo") if c else {"verdict": "uncertain", "reasons": ["找不到会话"]}
    g.pop("final", None)
    old = rec["leak_gate"].get("verdict")
    rec["leak_gate"] = g
    rec["gate_script_sha256"] = sha(HERE / "precise_gate.py")
    rec["regated"] = {"at": time.strftime("%F %T"), "old_verdict": old, "new_verdict": g.get("verdict"),
                      "why": "闸门误判修复：git merge-base 不再算打补丁；提交号改查本次工作区"}
    if g.get("verdict") == "contaminated":
        rec["unscored_reason"] = "leak gate: contaminated"
    elif rec.get("resolved") is None and not rec.get("zero_patch"):
        patch = (od / "model_patch.diff").read_text()
        assert hashlib.sha256(patch.encode()).hexdigest() == rec["patch_sha256"]
        h = harness(task, patch, f"ds{rep}", od / "eval")
        rec["eval"] = h
        rec.pop("unscored_reason", None)
        if h.get("error"):
            rec["unscored_reason"] = h["error"]
        else:
            rec["resolved"] = h["resolved"]
    (od / "record.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    CI.log(f"[rb regate] ★ {task} r{rep} gate {old}->{g.get('verdict')} resolved={rec.get('resolved')}")
    return rec


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "check":
        print(json.dumps(check(a[1]), ensure_ascii=False)[:1500])
    elif a[0] == "run":
        print(json.dumps(run(a[1], int(a[2])), ensure_ascii=False)[:1500])
    elif a[0] == "regate":
        print(json.dumps(regate(a[1], int(a[2])), ensure_ascii=False)[:800])
    elif a[0] == "reeval":
        print(json.dumps(reeval(a[1], int(a[2])), ensure_ascii=False)[:1500])
    elif a[0] == "finish":
        print(json.dumps(finish(a[1], int(a[2])), ensure_ascii=False)[:1500])
