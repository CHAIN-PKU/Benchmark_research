#!/usr/bin/env python3
"""Python 缺环境题：逐题从评测镜像拷 conda 环境 → 沙箱验证 → 自检 → 跑 2 次 → 清理。
   一次一道，盯磁盘；日志写 py_pipeline.log。"""
import csv, json, os, pathlib, shutil, subprocess, sys, time

HERE = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot")
sys.path.insert(0, str(HERE))
import claw_iso_rb as CI

PY = "/home/ubuntu/ai-market/venv/bin/python3"
LOG = HERE / "py_pipeline.log"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(time.strftime("[%F %T] ") + str(msg) + "\n")

def sh(cmd, timeout=7200, env=None):
    e = dict(os.environ); e.update(env or {})
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout, env=e, cwd=str(HERE))

def env_dir(task): return f"/opt/sbx/conda/{task}"

def image_of(task): return "swebench/sweb.eval.x86_64." + task.replace("__", "_1776_").lower() + ":latest"

def prep_env(task):
    img = image_of(task)
    log(f"prep {task} image={img}")
    sh(f"sudo docker image inspect {img} >/dev/null 2>&1 || sudo docker pull -q {img}", timeout=3600)
    name = "clawenv_" + task.replace("__", "_").replace("-", "_")
    sh(f"sudo docker rm -f {name} >/dev/null 2>&1")
    r = sh(f"sudo docker create --name {name} {img}")
    if r.returncode: log(f"create fail {task}: {r.stderr[-200:]}"); return False
    sh(f"sudo rm -rf {env_dir(task)}")
    r = sh(f"sudo docker cp {name}:/opt/miniconda3 {env_dir(task)}", timeout=3600)
    sh(f"sudo docker rm -f {name} >/dev/null 2>&1")
    if r.returncode:
        log(f"cp fail {task}: {r.stderr[-200:]}"); return False
    sh(f"echo copied_from_image | sudo tee {env_dir(task)}.source >/dev/null")
    log(f"prep ok {task} du={sh('sudo du -sh ' + env_dir(task)).stdout.strip()}")
    return True

def verify(task):
    r = CI.ROWS[task]
    p2p = r.get("PASS_TO_PASS") or []
    if isinstance(p2p, str): p2p = json.loads(p2p)
    test = p2p[0] if p2p else ""
    if "sphinx" in r["repo"]:
        cmd = f"tox --current-env -epy39 -v -- --tb=no -q '{test}' 2>&1 | tail -6"
    else:
        # django: "test_x (module.Class)" -> module.Class.test_x
        import re
        m = re.match(r"(\S+) \((\S+)\)", test or "")
        label = (m.group(2) + "." + m.group(1)) if m else test
        cmd = f"./tests/runtests.py --verbosity 1 --settings=test_sqlite --parallel 1 {label} 2>&1 | tail -8"
    chain = "claw_pyver__" + task
    c = CI.SB.chain_dir(chain)
    if c.exists(): shutil.rmtree(c, ignore_errors=True)
    try:
        info, ws, meta = CI.make_chain(chain, task)
        env = CI.SB.agent_env("deepseek/deepseek-v4.1-flash", None, 8776, "x", CI.sandbox_extra("python", task))
        out, err, killed, el = CI.run_in_sandbox(chain, ws, ["bash", "-c", "cd /home/coder/repo && " + cmd], env, 900, conda=task)
        ok = ("OK" in out) or ("passed" in out) or ("failed" in out and "error" not in out.lower())
        log(f"verify {task} ok={ok} el={round(el,1)} tail={out[-200:].replace(chr(10),' | ')}")
        return ok
    except Exception as e:
        log(f"verify EXC {task}: {type(e).__name__}: {str(e)[:200]}")
        return False
    finally:
        shutil.rmtree(c, ignore_errors=True)

def cleanup_env(task, remove_image=True):
    sh(f"sudo rm -rf {env_dir(task)} {env_dir(task)}.source")
    if remove_image:
        sh(f"sudo docker rmi {image_of(task)} >/dev/null 2>&1")
    # 清题目模板/工作区，防磁盘堆积
    sh(f"sudo rm -rf {HERE}/tpl/{task} /home/coder/chains/rb_dsh__{task}__r* /home/coder/chains/rb_gold_{task}* /home/coder/chains/claw_pyver__{task}")

def runs_done(task):
    n = 0
    d = HERE / "runs" / task
    for rep in sorted(d.glob("dsh_r*")) if d.exists() else []:
        rp = rep / "record.json"
        if (rep / "INVALID.json").exists() or not rp.exists(): continue
        try:
            j = json.loads(rp.read_text())
        except Exception:
            continue
        if j.get("resolved") in (True, False): n += 1
    return n

def main(tasks):
    log("pipeline start " + ",".join(tasks))
    for task in tasks:
        if runs_done(task) >= 2:
            log(f"skip done {task}"); continue
        if not prep_env(task):
            continue
        if not verify(task):
            log(f"env_fail {task} -> 清理并跳过"); cleanup_env(task); continue
        env = dict(os.environ, RB_CHANNEL="dsh", RB_DSH_PORT="8766")
        r = sh(f"{PY} ds_pilot.py check {task}", timeout=7200, env=env)
        sc = HERE / "runs" / task / "selfcheck" / "selfcheck.json"
        ok = False
        if sc.exists():
            try: ok = json.loads(sc.read_text()).get("selfcheck_ok") is True
            except Exception: ok = False
        log(f"check {task} rc={r.returncode} selfcheck_ok={ok}")
        if not ok:
            cleanup_env(task); continue
        for rep in (1, 2):
            if runs_done(task) >= 2: break
            d = HERE / "runs" / task / f"dsh_r{rep}"
            if (d / "record.json").exists(): continue
            rr = sh(f"{PY} ds_pilot.py run {task} {rep}", timeout=14400, env=env)
            log(f"run {task} r{rep} rc={rr.returncode}")
        log(f"task done {task} runs={runs_done(task)}")
        cleanup_env(task)
    log("pipeline end")

if __name__ == "__main__":
    tasks = sys.argv[1:]
    main(tasks)
