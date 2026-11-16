# rb 复制自 ai-market/scratchpad/claw_iso/claw_iso.py（2026-11-13），只改了路径和轮数/时限常量
#!/usr/bin/env python3
"""claw ranking 重测（2026-10-08，crc 19:48 批准）：沙箱跑 claw + 精确闸门 + 官方 harness + Opus 评委。

方案 (a)（main 20:2x 批准，/opt/sbx 不改）：
  * 工作区：fresh clone → checkout base → 删掉 base 之后的全部历史（同 claw_runner 10-08 版）。
  * 依赖：宿主机上以 ubuntu 联网预热进模板（tpl/<task>/{ws,home}），全部用与路径无关的缓存
    （GOMODCACHE / CARGO_HOME registry / node_modules / vendor / BUNDLE_PATH / COREPACK…）；
    预热绝不装被测项目自己的发布版，预热后扫描「项目同名包」并删掉。
  * 每条链：/home/coder/chains/claw_<tag>__<task>__iso/{home,tmp,ws}，从模板 cp -a；Rust 每链拷一份工具链（可写副本）。
  * agent：现有 agent_sandbox（uid coder、iptables、8798 只放 api.anthropic.com、私有 mount ns、私有 /tmp、全新 home）。
    DS→8766（与原 claw DS 记录一致），GLM→8767，Opus/Fable→OAuth 经 8798。
    claude -p 参数与 claw_runner 一致：120 轮、xhigh、2400s、--disallowedTools WebSearch WebFetch。
  * 闸门：claw_leak_20261008/precise_gate.scan（会话版）。clean→评测+评委；contaminated→作废；uncertain→评测+评委但待人工复核。
  * 评测/评委：claw_batch.run_harness（docker 全局锁，一次一个容器）/ claw_batch.judge（Opus 5 订阅）。
  * 新记录 claw_run_<tag>__<task>__iso.json；旧污染记录移到 ARCHIVE_claw_leak_20261008/。
用法：
  claw_iso.py tpl <task>...            预热模板
  claw_iso.py smoke <task>             沙箱内断网 + 离线工具链检查 + harness oracle/null
  claw_iso.py run <model> <task>       跑一对
  claw_iso.py batch <model> [n]        按清单跑（并发 2，load<4）
"""
import fcntl, hashlib, json, os, pathlib, re, shutil, subprocess, sys, threading, time

ROOT = pathlib.Path("/home/ubuntu/ai-market")
HERE = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot")   # rb: 复制版，不碰老目录
TAX = ROOT / "data/cold_start/taxonomy"
ARCH = TAX / "ARCHIVE_claw_leak_20261008"
TPL = HERE / "tpl"
SRC = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/claw_restore/bench-probe/vendor/claw-swe-bench/full-test.jsonl")
LOG = HERE / "claw_iso.log"
STATE = HERE / "phase_state.json"
sys.path.insert(0, str(ROOT / "scratchpad"))
sys.path.insert(0, str(ROOT / "scratchpad/sweevo_mt_20261008"))
sys.path.insert(0, str(ROOT / "scratchpad/claw_leak_20261008"))
import agent_sandbox as SB  # noqa: E402
import keyring  # noqa: E402

ROWS = {json.loads(l)["instance_id"]: json.loads(l) for l in open(SRC)}
PORT = {"deepseek/deepseek-v4.1-flash": 8776, "z-ai/glm-5.3-flashx": 8767, "moonshotai/kimi-k3.1-pro": 8777}   # 10-24 crc 批准：Kimi K3.1 Pro 走 8777（__any__ shim，fw.sh 已放行）
TURNS, TIMEOUT, EFFORT = int(os.environ.get("RB_TURNS", "500")), int(os.environ.get("RB_TIMEOUT", "10800")), os.environ.get("RB_EFFORT", "xhigh")   # rb: 默认 500 轮 / 3 小时；GLM 可用 RB_TURNS/RB_EFFORT 降档
PHASE_CAP = float(os.environ.get("CLAW_PHASE_CAP", "7.5"))   # crc：本阶段 OR 总上限（10-09：DS13 $5，GLM $8）
BAL_FLOOR = float(os.environ.get("CLAW_BAL_FLOOR", "3.0"))   # 开新一次前余额下限
HARD_FLOOR = float(os.environ.get("CLAW_HARD_FLOOR", "2.5"))   # 运行中余额跌破才杀；crc 10-09：不低于 $2.5
POLL = 30
PYTHON_HOLD = set()   # 20:4x main：/opt/sbx 已装 --conda，4 个镜像环境已拷到 /opt/sbx/conda/<task>，Python 题解禁
_lock = threading.Lock()
_ACTIVE = {"n": 0, "overlap_ids": set()}   # 在跑的 OR 运行：并发时余额差会串，改记 token 折算


def log(msg):
    line = f"[{time.strftime('%F %T')}] {msg}"
    print(line, flush=True)
    with _lock, open(LOG, "a") as f:
        f.write(line + "\n")


def sh(cmd, cwd=None, env=None, timeout=3600):
    return subprocess.run(cmd, shell=True, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)


BLOCKED_ENV = {"apache/lucene"}
# 2026-11-14 DSH：Maven 预热 + 离线单测已在 gson 验证通过（prewarm rc=[0,0,0]，沙箱 mvn_single_test_ok）。
# javaparser 是多模块工程：离线单测需要每个模块的 surefire provider，暂时仍阻断，待补模块级预热后放开。
JAVA_BUILD = {"google/gson": "java_maven", "reactivex/rxjava": "java_gradle",
              "javaparser/javaparser": "java_maven", "apache/druid": "java_maven"}


def lang_of(task):
    r = ROWS[task]
    repo = r["repo"].lower()
    if "caddy" in repo or "prometheus" in repo: return "go"
    if "bat" in repo or "coreutils" in repo: return "rust"
    if any(x in repo for x in ("carbon", "php-cs-fixer", "laravel")): return "php"
    if any(x in repo for x in ("jekyll", "fluentd", "fpm", "rubocop")): return "ruby"
    if any(x in repo for x in ("axios", "docusaurus", "preact", "immutable", "vuejs")): return "node"
    if "lombok" in repo: return "java"
    if "micropython" in repo: return "c_mp"
    if "valkey" in repo or "fmt" in repo: return "c"
    if "sphinx" in repo or "django" in repo: return "python"
    # rb 11-13：老流水线没覆盖的仓库，按语言归到已有预热方式；Maven 的 Java 项目（gson、druid）暂不支持
    RB = {"gin-gonic/gin": "go", "gohugoio/hugo": "go", "tokio-rs/tokio": "rust", "tokio-rs/axum": "rust",
          "nushell/nushell": "rust", "jqlang/jq": "c", "redis/redis": "c", "phpoffice/phpspreadsheet": "php",
          "mrdoob/three.js": "node",
          # 11-14 v3 新增：同语言、预热方式已有
          "astral-sh/ruff": "rust", "burntsushi/ripgrep": "rust", "fastlane/fastlane": "ruby", "faker-ruby/faker": "ruby",
          "babel/babel": "node", "hashicorp/terraform": "go", "nlohmann/json": "c",
          }
    if repo in RB: return RB[repo]
    if repo in JAVA_BUILD: return JAVA_BUILD[repo]
    # 2026-11-14 DSH 修：druid/gson/lucene/javaparser/rxjava 是 Maven/Gradle 项目，
    # java 预热只做了 lombok 的 ant deps，模板里没有它们的依赖；沙箱断网会编译不了，
    # 跑出来的失败是环境问题不是模型能力。在补 java_maven/java_gradle 预热前显式阻断，
    # 避免目录被建了一半、也避免 KeyError 把整道题半路崩掉。
    if repo in BLOCKED_ENV:
        raise RuntimeError(f"环境未支持：{repo} 需要 Maven/Gradle 依赖预热（待补 java_maven/java_gradle）")
    raise KeyError(task)


# ------------------------------------------------------------------ 环境变量（宿主机预热 / 沙箱内两套，结构一致）
def lang_env(lang, home):
    """home = 宿主机模板 home 路径（预热）或 /home/coder（沙箱内）。"""
    h = str(home)
    e = {"GOPATH": f"{h}/go", "GOMODCACHE": f"{h}/go/pkg/mod", "GOCACHE": f"{h}/.cache/go-build",
         "GOTOOLCHAIN": "local", "CARGO_HOME": f"{h}/.cargo", "RUSTUP_HOME": f"{h}/.rustup",
         "COMPOSER_HOME": f"{h}/.composer", "BUNDLE_PATH": f"{h}/.bundle-gems", "BUNDLE_APP_CONFIG": f"{h}/.bundle",
         "GEM_PATH": f"{h}/.bundle-gems/ruby/3.2.0", "npm_config_cache": f"{h}/.npm",
         "COREPACK_HOME": f"{h}/.cache/node/corepack", "YARN_CACHE_FOLDER": f"{h}/.cache/yarn",
         "PNPM_HOME": f"{h}/.local/share/pnpm", "npm_config_store_dir": f"{h}/.local/share/pnpm/store",
         "PUPPETEER_SKIP_DOWNLOAD": "1", "PUPPETEER_SKIP_CHROMIUM_DOWNLOAD": "1", "CYPRESS_INSTALL_BINARY": "0",
         "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD": "1", "IVY_HOME": f"{h}/.ivy2",
         # 2026-11-14 DSH：Maven/Gradle 项目的依赖缓存也放进模板 home，沙箱断网可复用
         "MAVEN_OPTS": f"-Dmaven.repo.local={h}/.m2/repository", "GRADLE_USER_HOME": f"{h}/.gradle"}
    path = f"{h}/.local/bin:{h}/.cargo/bin:{h}/go/bin:{h}/.bundle-gems/ruby/3.2.0/bin"
    # 2026-11-14 DSH：Maven/Gradle 老项目要 JDK11（宿主机默认 21 会把
    # -source 6 判死不支持；评测镜像里是 11，保持一致）
    if lang in ("java_maven", "java_gradle"):
        jh = "/usr/lib/jvm/java-11-openjdk-amd64"
        e["JAVA_HOME"] = jh
        path = f"{jh}/bin:" + path
    return e, path


def composer_root_version(ws):
    try:
        cj = json.loads((pathlib.Path(ws) / "composer.json").read_text())
        return ((cj.get("extra") or {}).get("branch-alias") or {}).get("dev-master")
    except Exception:
        return None


def sandbox_extra(lang, task=None):
    e, path = lang_env(lang, "/home/coder")
    if lang == "php" and task:
        v = composer_root_version(TPL / task / "ws")
        if v:
            e["COMPOSER_ROOT_VERSION"] = v
    if lang == "python":
        path = "/opt/miniconda3/envs/testbed/bin:" + path
        e["PYTHONPATH"] = "/home/coder/repo"   # 镜像里是 editable → /testbed，沙箱里没有 /testbed
    e.update({"GOPROXY": "off", "GOSUMDB": "off", "GOFLAGS": "-mod=mod", "CARGO_NET_OFFLINE": "true",
              "COMPOSER_DISABLE_NETWORK": "1", "npm_config_offline": "true", "COREPACK_ENABLE_NETWORK": "0",
              "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0", "BUNDLE_FROZEN": "false",
              "PATH": path + ":" + SB.SYS_PATH})
    return e


# ------------------------------------------------------------------ 模板：clone + 删未来历史 + 预热
SELF_PKG = {   # 项目自己的发布版：依赖里出现就删（例外：工作区自身的 symlink）
    "carbon": [r"vendor/nesbot/carbon$"], "php-cs-fixer": [r"vendor/friendsofphp/php-cs-fixer$"],
    "framework": [r"vendor/laravel/framework$", r"vendor/illuminate/[^/]+$"],
    "jekyll": [r"gems/jekyll-\d[^/]*$"], "fluentd": [r"gems/fluentd-\d[^/]*$"], "fpm": [r"gems/fpm-\d[^/]*$"],
    "rubocop": [r"gems/rubocop-\d[^/]*$"],
    "caddy": [r"github\.com/caddyserver/caddy(/v2)?@[^/]+$"], "prometheus": [r"github\.com/prometheus/prometheus@[^/]+$"],
    "bat": [r"registry/src/[^/]+/bat-\d[^/]*$"], "coreutils": [r"registry/src/[^/]+/(coreutils|uucore|uu_[a-z0-9_]+)-\d[^/]*$"],
    "lombok": [r"lombok[-.]?\d[^/]*\.jar$"],
}


def self_pkg_scan(task, ws, home, remove=True):
    name = ROWS[task]["repo"].split("/")[1]
    pats = [re.compile(p) for p in SELF_PKG.get(name, [])]
    if (pathlib.Path(ws) / "package.json").exists():   # node：根包 + workspace 包的名字（packages/*）
        names = set()
        for pj in [pathlib.Path(ws) / "package.json"] + sorted(pathlib.Path(ws).glob("packages/*/package.json")) \
                + sorted(pathlib.Path(ws).glob("packages/*/*/package.json")):
            try:
                n = json.loads(pj.read_text()).get("name")
            except Exception:
                n = None
            if n and not str(pj.parent).count("node_modules"):
                names.add(n)
        pats += [re.compile(r"node_modules/(.*/)?" + re.escape(n) + "$") for n in names]
    found = []
    if not pats:
        return found
    for root in (ws, home):
        for dp, dns, fns in os.walk(root):
            if "/.git" in dp:
                dns[:] = []
                continue
            for n in list(dns) + fns:
                p = os.path.join(dp, n)
                rel = os.path.relpath(p, root)
                if any(x.search(rel) for x in pats):
                    if os.path.islink(p):
                        continue          # 工作区 workspace 包的 symlink
                    found.append(p)
                    if n in dns:
                        dns.remove(n)
    if remove:
        for p in found:
            (shutil.rmtree if os.path.isdir(p) else os.unlink)(p)
    return found


PREWARM = {
    "go": ["go mod download -x 2>&1 | tail -3", "GOFLAGS=-mod=mod GOPROXY=off go list -deps -test ./... > /dev/null"],
    "rust": ["cargo fetch", "cargo metadata --offline --format-version 1 > /dev/null"],
    "php": ["composer install --no-interaction --no-progress || composer install --no-interaction --no-progress --ignore-platform-reqs || composer update --no-interaction --no-progress --ignore-platform-reqs",
            "test -f vendor/autoload.php"],
    "ruby": ["bundle install --jobs 3 || (rm -f Gemfile.lock; bundle install --jobs 3)", "bundle check"],
    "node": ["__node__"],
    "java": ["timeout 1500 ant -noinput deps || true"],
    "c_mp": ["make -C ports/unix submodules", "true"],
    "c": ["true"],
    "python": [],   # 环境 = 评测镜像的 /opt/miniconda3（只读挂载，sbx-run --conda <task>）
}


def _p2p_class(task):
    """从 PASS_TO_PASS 里挑一个测试目标，用来验证沙箱里真的能跑测试。
    数据集格式可能是 "Class.method" / "Class > method" / "package" / "Class"."""
    try:
        import json as _json
        p2p = ROWS[task].get("PASS_TO_PASS") or []
        if isinstance(p2p, str):
            p2p = _json.loads(p2p)
        for item in p2p:
            item = str(item).split(" > ")[0].strip()
            if not item:
                continue
            last = item.rsplit(".", 1)[-1]
            if last[:1].isupper():
                return item          # 完整类名
            return item + ".*"       # 包名 → 通配该包
    except Exception:
        pass
    return ""


def _gradle_filter(cls):
    """Gradle --tests 需要类名或通配；数据集里有时只给包名（末段小写），补 .*。"""
    if cls and cls.rsplit(".", 1)[-1][:1].islower():
        return cls + ".*"
    return cls


def java_maven_prewarm(ws, home, env, cls=""):
    """Maven：把依赖下到模板 home 的 .m2；多模块先 install，再在测试类所在模块离线跑一次。"""
    h = pathlib.Path(home)
    (h / ".m2").mkdir(parents=True, exist_ok=True)
    repo = f"{h}/.m2/repository"
    (h / ".m2/settings.xml").write_text(
        f"<settings><localRepository>{repo}</localRepository></settings>")
    steps = []
    # go-offline 在个别大工程（如 druid）会误报依赖解析失败；不当作致命错误，继续后面的编译/测试把真正需要的依赖拉全
    cmds0 = [f"mvn -B -q -DskipTests -Dmaven.repo.local={repo} dependency:go-offline",
             f"mvn -B -q -fae -DskipTests -Dmaven.repo.local={repo} test-compile"]
    for i, c in enumerate(cmds0):
        p = sh(c, cwd=str(ws), env=env, timeout=5400)
        steps.append({"cmd": c, "rc": p.returncode, "tail": (p.stdout + p.stderr)[-600:]})
        if p.returncode and i == 1:
            return steps
    if not cls:
        for f in sorted(ws.glob("**/src/test/java/**/*Test.java")):
            s = str(f)
            if "/src/test/java/" in s:
                cls = s.split("/src/test/java/", 1)[1][:-5].replace("/", ".")
                break
    if cls:
        # 多模块：先把各模块装进本地仓库（跳过测试），测试插件也随之缓存
        p = sh(f"mvn -B -q -fae -DskipTests -Dmaven.repo.local={repo} install", cwd=str(ws), env=env, timeout=5400)
        steps.append({"cmd": "mvn -DskipTests install", "rc": p.returncode, "tail": (p.stdout + p.stderr)[-400:]})
        simple = cls.split("#")[0].rsplit(".", 1)[-1]
        mod = ""
        for f in ws.glob("*/src/test/java/**/*.java"):
            try:
                if ("class " + simple) in f.read_text(errors="ignore"):
                    mod = f.parts[len(ws.parts)]
                    break
            except Exception:
                continue
        if mod:
            c = (f"cd {ws}/{mod} && mvn -B -q -Dmaven.repo.local={repo} -Dtest={simple} "
                 f"-DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test")
        else:
            c = (f"mvn -B -q -Dmaven.repo.local={repo} -Dtest={simple} "
                 f"-DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test")
        p = sh(c, cwd=str(ws), env=env, timeout=5400)
        steps.append({"cmd": c[-160:], "rc": p.returncode, "tail": (p.stdout + p.stderr)[-600:]})
        # 2026-11-14 Claude 选 a 的目的：把「所有模块」测试要用的插件缓存进模板。
        # 但 druid 这类大工程完整跑测试会超过 30 分钟，所以用「把测试过滤成不存在的类」跑一遍
        # test 阶段：每个模块的 surefire/测试插件都会解析并下载，实际几乎不跑测试，几十秒完成。
        cfull = (f"mvn -B -fae -Dmaven.repo.local={repo} "
                 f"-Dtest=NoSuchTestClass__claw_warmup -Dsurefire.failIfNoSpecifiedTests=false "
                 f"-DfailIfNoTests=false test")
        p = sh(cfull, cwd=str(ws), env=env, timeout=1800)
        steps.append({"cmd": "mvn test (plugin warm, filtered no-match)", "rc": p.returncode,
                      "tail": (p.stdout + p.stderr)[-800:]})
    return steps


def _gradle_project_path(ws, simple):
    """按测试类所在目录推断 Gradle 子项目路径（如 :lucene:core）。"""
    for f in ws.glob("**/src/test/java/**/*.java"):
        try:
            if ("class " + simple) in f.read_text(errors="ignore"):
                rel = f.relative_to(ws)
                parts = list(rel.parts)
                idx = parts.index("src")
                proj = parts[:idx]
                if proj:
                    return ":" + ":".join(proj)
        except Exception:
            continue
    return ""


def java_gradle_prewarm(ws, home, env, cls=""):
    """Gradle：wrapper 下发行版和依赖，再 testClasses，再在线跑一个测试（缓存 test 任务所需插件）。"""
    h = pathlib.Path(home)
    (h / ".gradle").mkdir(parents=True, exist_ok=True)
    env = dict(env, GRADLE_USER_HOME=f"{h}/.gradle")
    steps = []
    simple0 = (cls.split("#")[0].rsplit(".", 1)[-1] if cls else "")
    proj = _gradle_project_path(ws, simple0) if simple0 else ""
    cmds = ["./gradlew --no-daemon --refresh-dependencies dependencies",
            "./gradlew --no-daemon testClasses"]
    if proj and simple0:
        cmds.append('./gradlew --no-daemon %s:test --tests "%s" -x javadoc' % (proj, simple0))
    for c in cmds:
        p = sh(c, cwd=str(ws), env=env, timeout=5400)
        steps.append({"cmd": c, "rc": p.returncode, "tail": (p.stdout + p.stderr)[-600:]})
        if p.returncode and "dependencies" in c:
            break
    # 2026-11-14：同 Maven，在线跑一遍完整 test（--continue，失败也继续），缓存所有子项目测试依赖
    p = sh("./gradlew --no-daemon test --continue", cwd=str(ws), env=env, timeout=1800)
    steps.append({"cmd": "./gradlew test --continue (full)", "rc": p.returncode,
                  "tail": (p.stdout + p.stderr)[-800:]})
    return steps


def node_prewarm(ws, env):
    pj = json.loads((ws / "package.json").read_text())
    pm = str(pj.get("packageManager") or "")
    cmds = []
    if (ws / "pnpm-lock.yaml").exists():
        ver = pm.split("@")[1].split("+")[0] if pm.startswith("pnpm@") else "8"
        cmds = [f"npm i -g --prefix $HOME/.local pnpm@{ver}", "pnpm install --frozen-lockfile || pnpm install"]
    elif (ws / "yarn.lock").exists():
        cmds = ["npm i -g --prefix $HOME/.local yarn@1", "yarn install --frozen-lockfile --network-timeout 600000 || yarn install --network-timeout 600000"]
    else:
        cmds = ["npm ci --no-audit --no-fund || npm ci --no-audit --no-fund --ignore-scripts || npm install --no-audit --no-fund --legacy-peer-deps"]
    out = []
    for c in cmds:
        p = sh(c, cwd=str(ws), env=env, timeout=3600)
        out.append({"cmd": c, "rc": p.returncode, "tail": (p.stdout + p.stderr)[-600:]})
        if p.returncode:
            break
    return out


def make_tpl(task, force=False):
    r = ROWS[task]
    lang = lang_of(task)
    t = TPL / task
    meta_f = t / "meta.json"
    if meta_f.exists() and not force:
        return json.loads(meta_f.read_text())
    if disk_pct() >= 93:
        raise RuntimeError(f"磁盘 {disk_pct():.1f}% >= 93%，不建模板")
    if t.exists():
        shutil.rmtree(t)
    ws, home = t / "ws", t / "home"
    home.mkdir(parents=True)
    log(f"[tpl] {task} clone {r['repo']} @ {r['base_commit'][:10]} lang={lang}")
    c = sh(f"git clone -q https://github.com/{r['repo']}.git '{ws}'", timeout=3600)
    if c.returncode:
        raise RuntimeError(f"clone 失败 {c.stderr[-300:]}")
    sh(f"git checkout -q {r['base_commit']}", cwd=str(ws))
    meta = {"task": task, "lang": lang, "base": r["base_commit"], "steps": []}
    if lang == "c_mp":   # 子模块要在删 remote 之前按 .gitmodules 拉（子模块是别的仓库，不含本项目未来历史）
        p = sh("make -C ports/unix submodules", cwd=str(ws), timeout=1800)
        meta["steps"].append({"cmd": "make -C ports/unix submodules", "rc": p.returncode, "tail": (p.stdout + p.stderr)[-400:]})
    iso = sh("git checkout -q --detach && git remote remove origin; "
             "git for-each-ref --format='%(refname)' refs/heads refs/tags refs/remotes | xargs -r -n1 git update-ref -d; "
             "git stash clear; git reflog expire --expire=now --all && git gc -q --prune=now", cwd=str(ws), timeout=3600)
    left = sh(f"git rev-list --all --not {r['base_commit']} | head -1", cwd=str(ws)).stdout.strip()
    if left:
        raise RuntimeError(f"工作区隔离失败：base 之后还有提交 {left[:10]} {iso.stderr[-200:]}")
    meta["history_stripped"] = True
    # Rust 工具链：模板里只放 rustup 设置和 cargo 代理；工具链本体在建链时拷（每链一份可写副本）
    env = dict(os.environ)
    e, path = lang_env(lang, home)
    env.update(e)
    env["HOME"] = str(home)
    env["PATH"] = path + ":/usr/local/bin:/usr/bin:/bin"
    if lang == "php" and composer_root_version(ws):
        env["COMPOSER_ROOT_VERSION"] = composer_root_version(ws)
        meta["composer_root_version"] = env["COMPOSER_ROOT_VERSION"]
    if lang == "rust":
        (home / ".cargo/bin").mkdir(parents=True)
        for f in pathlib.Path("/home/ubuntu/.cargo/bin").iterdir():
            os.symlink(os.readlink(f), home / ".cargo/bin" / f.name) if f.is_symlink() else shutil.copy2(f, home / ".cargo/bin" / f.name)
        env["RUSTUP_HOME"] = "/home/ubuntu/.rustup"     # 预热时直接用宿主机的
    if lang == "node":
        meta["steps"] += node_prewarm(ws, env)
    elif lang == "java_maven":
        meta["steps"] += java_maven_prewarm(ws, home, env, _p2p_class(task))
    elif lang == "java_gradle":
        meta["steps"] += java_gradle_prewarm(ws, home, env, _p2p_class(task))
    elif lang != "c_mp":
        for cmd in PREWARM[lang]:
            p = sh(cmd, cwd=str(ws), env=env, timeout=3600)
            meta["steps"].append({"cmd": cmd, "rc": p.returncode, "tail": (p.stdout + p.stderr)[-600:]})
    # 预热改了被跟踪文件 → 还原；新生成的未跟踪文件（lockfile 等）→ 写进 .git/info/exclude，不进 agent 的 diff
    st = sh("git status --porcelain --untracked-files=normal", cwd=str(ws)).stdout.splitlines()
    mod = [l[3:] for l in st if not l.startswith("??")]
    unt = [l[3:] for l in st if l.startswith("??")]
    if mod:
        sh("git checkout -- . && git submodule update --init --recursive >/dev/null 2>&1 || true", cwd=str(ws))
    if unt:
        with open(ws / ".git/info/exclude", "a") as f:
            f.write("\n# claw_iso prewarm artefacts\n" + "\n".join("/" + u.rstrip("/") for u in unt) + "\n")
    meta["reverted_tracked"] = mod
    meta["excluded_untracked"] = unt
    meta["self_pkg_removed"] = self_pkg_scan(task, ws, home)
    left = sh(f"git rev-list --all --not {r['base_commit']} | head -1", cwd=str(ws)).stdout.strip()
    assert not left, "预热后出现 base 之后的提交"
    meta["du"] = sh(f"du -sh '{t}'").stdout.split()[0]
    meta["at"] = time.strftime("%F %T")
    meta_f.write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    log(f"[tpl] {task} done du={meta['du']} rc={[s['rc'] for s in meta['steps']]} self_pkg={len(meta['self_pkg_removed'])} excl={unt[:5]}")
    return meta


# ------------------------------------------------------------------ 建链 / 启动
def chain_name(model, task, suffix="__iso"):
    return f"claw_{model.replace('/', '_')}__{task}{suffix}"


def make_chain(chain, task):
    meta = make_tpl(task)
    info = SB.ensure_isolation()
    c = SB.chain_dir(chain)
    if c.exists():
        raise SystemExit(f"{c} 已存在")
    (c / "tmp").mkdir(parents=True)
    t = TPL / task
    r1 = sh(f"cp -a '{t}/home' '{c}/home' && cp -a '{t}/ws' '{c}/ws'", timeout=3600)
    if r1.returncode:
        raise RuntimeError(r1.stderr[-300:])
    (c / "home/.gitconfig").write_text("[user]\n\tname = dev\n\temail = dev@example.com\n")
    if meta["lang"] == "rust":
        r2 = sh(f"mkdir -p '{c}/home/.rustup' && cp -a /home/ubuntu/.rustup/settings.toml /home/ubuntu/.rustup/toolchains '{c}/home/.rustup/'", timeout=1800)
        if r2.returncode:
            raise RuntimeError(r2.stderr[-300:])
    # 起链前扫描：agent 可见的地方不得有项目自己的发布版 / 上游 clone / gold 文件
    info["self_pkg_visible"] = self_pkg_scan(task, c / "ws", c / "home", remove=False)
    if info["self_pkg_visible"]:
        raise SystemExit(f"起链前扫描命中项目自身发布版：{info['self_pkg_visible'][:5]}")
    return info, c / "ws", meta


def run_in_sandbox(chain, ws, argv, env, timeout, guard=None, conda=None):
    SB.write_env(chain, env)
    SB.set_owner(chain, ws, SB.AGENT_USER)
    t0 = time.time()
    cmd = SB.launcher(chain, ws, argv, venv="none")
    if conda:
        i = cmd.index("--venv")
        cmd[i:i] = ["--conda", conda]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, cwd="/", start_new_session=True)
    killed = None
    out = err = ""
    while True:
        try:
            out, err = p.communicate(timeout=POLL)
            break
        except subprocess.TimeoutExpired:
            if time.time() - t0 > timeout:
                killed = "timeout"
            elif guard:
                try:
                    killed = guard()
                except Exception as e:  # noqa: BLE001
                    log(f"guard error {e}")
            if killed:
                SB.reap(chain)
                out, err = p.communicate()
                err = (err or "") + f"\nKILLED: {killed}"
                break
    SB.reap(chain)
    SB.set_owner(chain, ws, "ubuntu")
    return out or "", err or "", killed, round(time.time() - t0, 1)


def or_total():
    b = [s["balance"] for s in keyring.status() if s.get("balance") is not None]
    return max(b) if b else None   # 10-09 20:2x：pick_key 用余额最多的那把；另一把是 -0.31 的透支 key，不能相加


def own_phase_spend(model, st):
    """本阶段（phase_state.at 之后）本模型 `__iso` 记录（含 .crash1/.killed 草稿）的 token 折算花费。"""
    import cost_lib as CL
    t0 = time.mktime(time.strptime(st["at"], "%Y-%m-%d %H:%M:%S"))
    tag = model.replace("/", "_")
    tot = 0.0
    for f in TAX.glob(f"claw_run_{tag}__*__iso*.json"):
        if f.stat().st_mtime < t0:
            continue
        try:
            r = json.loads(f.read_text())
        except Exception:
            continue
        tot += CL.token_cost(model, r.get("usage")) or 0.0
    return tot


def phase_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    st = {"start_balance": or_total(), "at": time.strftime("%F %T")}
    STATE.write_text(json.dumps(st))
    return st


# ------------------------------------------------------------------ 冒烟
JAVA_MAVEN_SMOKE = r'''
set -o pipefail
mvn -o -q -B -DskipTests -Dmaven.repo.local=$HOME/.m2/repository test-compile 2>&1 | tail -3 && echo mvn_root_testcompile_ok
if [ -n "$RB_TEST_CLASS" ]; then CLS="$RB_TEST_CLASS"; else T=$(find . -path '*/src/test/java/*Test.java' | head -1); CLS=$(echo "$T" | sed 's#.*/src/test/java/##; s#\.java##; s#/#.#g'); fi
echo "single test: $CLS"
SIMPLE=$(echo "$CLS" | sed 's/.*[.#]//')
MOD=$(grep -rl --include=*.java "class $SIMPLE" . 2>/dev/null | grep '/src/test/java/' | head -1 | cut -d/ -f2)
if [ -n "$MOD" ]; then cd "$MOD" && echo "module: $MOD"; fi
if mvn -o -q -B -Dmaven.repo.local=$HOME/.m2/repository -Dtest="$SIMPLE" -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test 2>&1 | tail -4; then echo mvn_single_test_ok; else echo mvn_single_test_FAIL; fi
cd /home/coder/repo
MOD2=$(find . -path '*/src/test/java/*Test.java' 2>/dev/null | cut -d/ -f2 | sort -u | grep -v "^$MOD$" | head -1)
if [ -n "$MOD2" ]; then
  T2=$(find "./$MOD2" -path '*/src/test/java/*Test.java' | head -1)
  SIMPLE2=$(basename "$T2" .java)
  echo "other module test: $MOD2 / $SIMPLE2"
  cd "$MOD2" && if mvn -o -q -B -Dmaven.repo.local=$HOME/.m2/repository -Dtest="$SIMPLE2" -DfailIfNoTests=false -Dsurefire.failIfNoSpecifiedTests=false test 2>&1 | tail -4; then echo mvn_other_module_test_ok; else echo mvn_other_module_test_FAIL; fi
fi
'''
JAVA_GRADLE_SMOKE = r'''
set -o pipefail
./gradlew --offline -q testClasses 2>&1 | tail -3 && echo gradle_offline_testclasses_ok
if [ -n "$RB_TEST_CLASS" ]; then CLS="$RB_TEST_CLASS"; else T=$(find . -path '*/src/test/java/*Test.java' | head -1); CLS=$(basename "$T" .java); fi
echo "single test: $CLS"
SIMPLE=$(echo "$CLS" | sed 's/.*[.#]//')
T=$(grep -rl --include=*.java "class $SIMPLE" . 2>/dev/null | grep '/src/test/java/' | head -1)
PROJ=""
if [ -n "$T" ]; then PROJ=":"$(echo "$T" | sed 's#^\./##' | awk -F/  '{p=""; for(i=1;i<NF;i++){if($i=="src")break;p=p":"$i} print substr(p,2)}'); fi
echo "project: $PROJ"
if [ -n "$PROJ" ]; then
  if ./gradlew --offline "$PROJ:test" --tests "$SIMPLE" 2>&1 | tail -4; then echo gradle_single_test_ok; else echo gradle_single_test_FAIL; fi
fi
MOD2=$(find . -path '*/src/test/java/*Test.java' 2>/dev/null | sed 's#^\./##' | awk -F/ '{p="";for(i=1;i<NF;i++){if($i=="src")break;p=p"/"$i};print substr(p,2)}' | sort -u | grep -v "^$(echo $PROJ | sed 's/^://; s/:/\//g')$" | head -1)
if [ -n "$MOD2" ]; then
  T2=$(find "./$MOD2" -path '*/src/test/java/*Test.java' | head -1); SIMPLE2=$(basename "$T2" .java)
  echo "other module test: $MOD2 / $SIMPLE2"
  PROJ2=":"$(echo "$MOD2" | sed 's#/#:#g')
  if ./gradlew --offline "$PROJ2:test" --tests "$SIMPLE2" 2>&1 | tail -4; then echo gradle_other_module_test_ok; else echo gradle_other_module_test_FAIL; fi
fi
'''
SMOKE_CHECK = {
    "go": "go build ./... && go test -count=1 -run '^$' ./modules/caddyhttp/... 2>&1 | tail -3",
    "rust": "cargo check --offline 2>&1 | tail -3",
    "php": "php vendor/bin/phpunit --version",
    "ruby": "bundle exec ruby -e 'puts :bundle_ok'",
    "node": "ls node_modules | wc -l && (pnpm --version || true) && node -e \"require('vitest/package.json');console.log('vitest ok')\" 2>/dev/null || node -e \"console.log(Object.keys(require('./package.json').devDependencies||{}).filter(d=>{try{require.resolve(d+'/package.json');return true}catch(e){return false}}).length+' devDeps resolvable')\"",
    "java": "ls lib 2>/dev/null | head -3; ant -noinput -p | head -3",
    "java_maven": JAVA_MAVEN_SMOKE,
    "java_gradle": JAVA_GRADLE_SMOKE,
    "c_mp": "make -C mpy-cross -j2 2>&1 | tail -2",
    "python": "which python; python -V; python -c 'import sys,os;m=__import__(\"sphinx\" if os.path.isdir(\"sphinx\") else \"django\");print(m.__file__, getattr(m,\"__version__\",None))' && python -m pytest --version 2>&1 | tail -1; pip list 2>/dev/null | grep -iE '^(sphinx|django) '",
    "c": "if [ -f include/fmt/format.h ]; then g++ -std=c++11 -Iinclude -c src/format.cc -o /tmp/f.o && echo fmt_ok; else make -j2 -C src valkey-cli 2>&1 | tail -2; fi",
}
NET_PROBE = r"""
echo "uid=$(id -u) home=$HOME"; ls /home; ls /home/ubuntu 2>&1 | head -1; ls /tmp | head
for u in https://github.com https://pypi.org/simple/ https://registry.npmjs.org/ https://proxy.golang.org https://repo.packagist.org https://rubygems.org https://crates.io https://api.anthropic.com; do
  printf '%s -> ' $u; curl -sS -m 8 -o /dev/null -w '%{http_code}\n' $u 2>&1 | tail -1; done
printf 'direct 140.82.112.3:443 -> '; curl -sS -m 8 --noproxy '*' -o /dev/null -w '%{http_code}\n' https://140.82.112.3 2>&1 | tail -1
printf 'dns -> '; getent hosts github.com || echo no-dns
printf 'git ls-remote -> '; timeout 20 git ls-remote https://github.com/git/git HEAD 2>&1 | tail -1
printf 'git ls-remote (protocol allowed) -> '; GIT_ALLOW_PROTOCOL=https timeout 20 git ls-remote https://github.com/git/git HEAD 2>&1 | tail -1
printf 'go get -> '; (cd /tmp && GOFLAGS= GOPROXY=https://proxy.golang.org timeout 20 go mod download -json golang.org/x/text@latest 2>&1 | grep -E '"(Error|Zip)"' | head -1)
printf 'pip -> '; timeout 20 python3 -m pip download --index-url https://pypi.org/simple six -d /tmp/x 2>&1 | tail -1
printf 'npm view -> '; timeout 30 npm view --offline=false left-pad version 2>&1 | tail -1
"""


def smoke(task):
    lang = lang_of(task)
    chain = f"claw_smoke__{task}"
    c = SB.chain_dir(chain)
    if c.exists():
        sh(f"sudo -n rm -rf '{c}'")
    info, ws, meta = make_chain(chain, task)
    env = SB.agent_env("deepseek/deepseek-v4.1-flash", None, 8776, "x", sandbox_extra(lang, task))
    _cls = _p2p_class(task)
    if lang == "java_gradle":
        _cls = _gradle_filter(_cls)
    script = NET_PROBE + "\nexport RB_TEST_CLASS='" + _cls + "'\necho '=== toolchain (offline)'\n" + SMOKE_CHECK[lang] + "\necho rc=$?\n"
    out, err, killed, el = run_in_sandbox(chain, ws, ["bash", "-c", script], env, 1500,
                                          conda=task if lang == "python" else None)
    res = {"task": task, "lang": lang, "sandbox_out": out[-4000:], "sandbox_err": err[-800:], "el": el,
           "prewarm": [{k: s[k] for k in ("cmd", "rc")} for s in meta["steps"]], "self_pkg_removed": meta["self_pkg_removed"]}
    # harness：oracle（gold）应 resolved，null（只改 README 的空补丁）应不 resolved
    import claw_batch as CB
    r = ROWS[task]
    ds = pathlib.Path(f"/tmp/claw_ds_{task}.json")
    ds.write_text(json.dumps([_ds_row(r)], ensure_ascii=False))
    for kind, patch in (("oracle", r["patch"]), ("null", _noop_patch(c / "ws"))):
        pp = pathlib.Path(f"/tmp/claw_pred_smoke_{kind}_{task}.jsonl")
        pp.write_text(json.dumps({"instance_id": task, "model_patch": patch, "model_name_or_path": f"smoke_{kind}"}))
        h = CB.run_harness(task, f"smoke_{kind}", {"pred_path": str(pp), "dataset_path": str(ds)}, log)
        res[kind] = {k: h.get(k) for k in ("passed", "total", "regressed", "resolved", "patch_applied")} if h else None
    sh(f"sudo -n rm -rf '{c}'")
    (HERE / f"smoke_{task}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    log(f"[smoke] {task} oracle={res['oracle']} null={res['null']}")
    return res


def _noop_patch(ws):
    for n in ("README.md", "README.markdown", "README.rst", "README"):
        if (ws / n).exists():
            return (f"diff --git a/{n} b/{n}\n--- a/{n}\n+++ b/{n}\n@@ -1 +1,2 @@\n"
                    + "+ \n" + " " + (ws / n).read_text(errors="replace").splitlines()[0] + "\n")
    # 2026-11-14 DSH：有些仓库没有 README（javaparser），空补丁改为新增一个无关文件
    return ("diff --git a/dsh_noop.txt b/dsh_noop.txt\nnew file mode 100644\n"
            "--- /dev/null\n+++ b/dsh_noop.txt\n@@ -0,0 +1 @@\n+dsh noop probe\n")


def _ds_row(r):
    return {"instance_id": r["instance_id"], "repo": r["repo"], "base_commit": r["base_commit"], "patch": r["patch"],
            "test_patch": r["test_patch"], "problem_statement": r.get("problem_statement", ""),
            "hints_text": r.get("hints_text", ""), "created_at": r.get("created_at", ""), "version": str(r.get("version", "")),
            "FAIL_TO_PASS": json.dumps(r["FAIL_TO_PASS"]) if isinstance(r["FAIL_TO_PASS"], list) else r["FAIL_TO_PASS"],
            "PASS_TO_PASS": json.dumps(r.get("PASS_TO_PASS", [])) if isinstance(r.get("PASS_TO_PASS"), list) else r.get("PASS_TO_PASS", "[]"),
            "environment_setup_commit": r["base_commit"]}


# ------------------------------------------------------------------ 一对
def plan():
    return json.loads((HERE / "plan_full.json").read_text())   # 22:1x 起用 plan_full.json（plan.json 被裁成旧进程的在途对）


# crc 22:06：钱不够时先跑「决定格子第一名」的对：5 道 medium 重灾题 → 其余 medium/hard → easy
PRIORITY = ["briannesbitt__carbon-2813", "briannesbitt__carbon-3005", "jekyll__jekyll-8771", "micropython__micropython-12158",
            "php-cs-fixer__php-cs-fixer-8075",
            "caddyserver__caddy-6115", "projectlombok__lombok-3571", "rubocop__rubocop-13560", "sphinx-doc__sphinx-9320",
            "uutils__coreutils-6377", "axios__axios-5316", "axios__axios-6539", "facebook__docusaurus-9183",
            "jekyll__jekyll-8761", "jordansissel__fpm-1829", "prometheus__prometheus-9248"]


def run_pair(model, task, retry=False):
    import claw_batch as CB
    assert CB.JUDGE_VERSION == os.environ.get("CLAW_EXPECT_JUDGE", "v2.1_20261009"), CB.JUDGE_VERSION
    import precise_gate as PG
    import or_cost
    sys.path.insert(0, "/home/ubuntu/ai-market/cold_start/python")
    import eval_backend_vertical as EBV
    tag = model.replace("/", "_")
    out_f = TAX / f"claw_run_{tag}__{task}__iso.json"
    if out_f.exists() and json.loads(out_f.read_text()).get("done"):
        log(f"skip {model} {task}（已有）")
        return json.loads(out_f.read_text())
    pl = [p for p in plan() if p["model"] == model and p["task"] == task][0]
    lang = lang_of(task)
    chain = chain_name(model, task, "__iso" + ("_retry" if retry else ""))
    if SB.chain_dir(chain).exists():
        sh(f"sudo -n rm -rf '{SB.chain_dir(chain)}'")
    info, ws, meta = make_chain(chain, task)
    r = ROWS[task]
    prompt = f"""这个仓库里有一个问题需要你解决。

## 问题描述
{(r.get('problem_statement') or '')[:8000]}

**要求：**
- 直接改产品代码把问题解决掉，不要只改测试
- 只做这个问题要求的改动，不要顺手重构无关代码
- 保持仓库现有的代码风格和结构
"""
    is_or = not model.startswith("claude-")
    key = keyring.pick_key() if is_or else None
    env = SB.agent_env(model, None, PORT.get(model), key, sandbox_extra(lang, task))
    argv = [SB.CLAUDE_BIN, "-p", "--model", model, "--permission-mode", "bypassPermissions", "--effort", EFFORT,
            "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--max-turns", str(TURNS),
            "--disallowedTools", "WebSearch", "WebFetch", "--output-format", "json", prompt]
    st = phase_state()
    b0 = or_total() if is_or else None
    if is_or and b0 is not None:
        # 10-09 main：key 与 held-out 重测、OR-auto 对照线共用 → 阶段上限按**本阶段自己的记录 token 折算**卡，余额差只作参考
        own = own_phase_spend(model, st)
        if own >= PHASE_CAP - 0.3:   # 留 $0.3 给在途的另一路
            raise SystemExit(f"阶段 {model} 自己的 token 折算花费 ${own:.2f} >= ${PHASE_CAP}（余额差 ${st['start_balance'] - b0:.2f} 仅参考），不再开新的")
        if b0 < BAL_FLOOR:
            raise SystemExit(f"OR 余额 ${b0:.2f} < ${BAL_FLOOR}，不再开新的")

    def guard():
        b = or_total()
        if b is not None and b < HARD_FLOOR:
            return f"balance ${b:.2f} < hard floor {HARD_FLOOR}"
        return None

    rid = f"{model}|{task}"
    if is_or:
        with _lock:
            _ACTIVE["n"] += 1
            if _ACTIVE["n"] > 1:
                _ACTIVE["overlap_ids"] |= {rid, "__any_active__"}
            _ACTIVE.setdefault("ids", set()).add(rid)
            if len(_ACTIVE["ids"]) > 1:
                _ACTIVE["overlap_ids"] |= set(_ACTIVE["ids"])
    log(f"— {model} / {task} chain={chain} lang={lang}")
    out, err, killed, el = run_in_sandbox(chain, ws, argv, env, TIMEOUT, guard if is_or else None,
                                          conda=task if lang == "python" else None)
    if is_or:
        time.sleep(10)
    b1 = or_total() if is_or else None
    try:
        j = json.loads(out)
    except Exception:
        j = {}
    d = sh(f"git add -A && git diff --cached {r['base_commit']}", cwd=str(ws))
    patch, artifacts = exclude_artifacts(ws, r["base_commit"], d.stdout or "")
    (HERE / "preds").mkdir(exist_ok=True)
    pp = HERE / "preds" / f"{tag}__{task}__iso.{time.strftime('%Y%m%d_%H%M%S')}.jsonl"   # 每条记录独立，不共用 /tmp
    pp.write_text(json.dumps({"instance_id": task, "model_patch": patch, "model_name_or_path": tag}, ensure_ascii=False))
    dp = pathlib.Path(f"/tmp/claw_ds_{task}.json")
    dp.write_text(json.dumps([_ds_row(r)], ensure_ascii=False))
    rec = {"task_id": task, "model": model, "benchmark": "claw-swe-bench", "language": r.get("language"), "repo": r["repo"],
           "elapsed_s": el, "turns": j.get("num_turns"), "cost_usd_cc_reported": j.get("total_cost_usd"),
           "usage": j.get("usage") or {}, "patch_chars": len(patch), "workdir": str(ws),
           "agent_ok": j.get("is_error") is not True and not killed, "result_head": str(j.get("result") or err[-300:])[:400],
           "stop_reason": j.get("stop_reason"), "terminal_reason": j.get("terminal_reason"),
           "pred_path": str(pp), "dataset_path": str(dp), "bg_wait_resumes": [], "session_id": j.get("session_id"),
           "run_suffix": "__iso", "killed": killed, "artifacts_excluded": artifacts, "leaf_node": pl["leaf_node"],
           "retest_of": pl["old_files"], "sandbox": {"method": info.get("method"), "chain": chain,
                                                     "shim_port": PORT.get(model), "lang": lang,
                                                     "prewarm": [{k: s[k] for k in ("cmd", "rc")} for s in meta["steps"]],
                                                     "self_pkg_removed": meta["self_pkg_removed"],
                                                     "excluded_untracked": meta["excluded_untracked"],
                                                     "claude_version": info.get("claude_version")}}
    if is_or:
        with _lock:
            _ACTIVE["n"] -= 1
            _ACTIVE["ids"].discard(rid)
            overlapped = rid in _ACTIVE["overlap_ids"]
            _ACTIVE["overlap_ids"].discard(rid)
        or_cost.record_spend(rec, model, b0, b1)
        rec["or_balance_before_after"] = [b0, b1]
        if overlapped:   # 另一路 OR 同时在跑：余额差含别人的花费 → 记 token 折算（cost_lib 口径，含缓存折扣）
            import cost_lib as CL
            rec["or_balance_delta_raw"] = rec.get("or_spend_usd")
            rec["or_spend_usd"] = CL.token_cost(model, rec.get("usage"))
            rec["cost_source"] = "token_est_concurrent_or_run"
    out_text = (out + err).lower()
    if any(q in out_text for q in CB.QUOTA_MARKS) or any(q in rec["result_head"].lower() for q in CB.QUOTA_MARKS):
        out_f.with_suffix(".quota.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        raise CB.QuotaWall(rec["result_head"][:200])
    if killed and killed != "timeout":
        rec["unscored_reason"] = f"budget kill: {killed}"
        out_f.with_suffix(".killed.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        raise SystemExit(f"预算熔断：{killed}")
    # 闸门（会话版精确闸门）
    sf = SB.project_dir(chain) / f"{j.get('session_id')}.jsonl"
    if not sf.exists():
        cands = sorted(SB.project_dir(chain).glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
        sf = cands[-1] if cands else None
    g = PG.scan(sf, task, "/home/coder/repo") if sf else {"verdict": "uncertain", "reasons": ["找不到会话"]}
    g.pop("final", None)
    rec["leak_gate"] = dict(g, gate="precise_gate.scan(会话版) 2026-10-08", session_file=str(sf))
    rec["leak_scan_sandbox"] = {k: v for k, v in SB.scan_transcripts(SB.project_dir(chain)).items() if k in ("verdict", "n_hard", "n_strong", "hard")}
    annotate_gate(rec)
    crashy = (not rec["agent_ok"]) or ((rec["turns"] or 0) <= 1)
    if not patch.strip() and crashy and not retry:
        log(f"  ⚠ 零产出且没正常退出，补跑一次：{rec['result_head'][:120]}")
        out_f.with_suffix(".crash1.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
        return run_pair(model, task, retry=True)
    if g["verdict"] == "contaminated":
        rec.update({"final_100": None, "harness_score": None,
                    "unscored_reason": "leak_gate（精确闸门）：会话里拿到了上游参考解，本条作废"})
    elif not patch.strip():
        rec.update({"harness_score": 0.0, "llm_score": 0.0, "final_100": 0.0,
                    "zero_reason": "agent 正常结束但没有任何代码改动" if not crashy else "agent 两次都零产出，按规矩记 0 分"})
    else:
        h = CB.run_harness(task, model, rec, log)
        drop_eval_image(task)
        if not h:
            rec["unscored_reason"] = "harness 没产出 report（待重试）"
        else:
            rec.update(h)
            if not rec.get("total"):
                rec["harness_score"] = None
                rec["unscored_reason"] = "官方目标测试收集到 0 个可执行用例；客观分无法测量，不计入均分"
            else:
                hs = 100.0 * rec["passed"] / rec["total"]
                if rec.get("regressed"):
                    hs = min(hs, 60.0)
                _pt = CB._patch_text(str(pp))
                assert len(_pt) == len(patch), f"pred 文件被改过：{len(_pt)} != patch_chars {len(patch)}"
                rec["_patch"], rec["_patch_full"] = _pt[:20000], _pt
                prof = EBV.resolve_profile({"leaf_node": pl["leaf_node"], "task_id": task, "description": ""})
                raw, parsed = CB.judge(r, rec, prof, log)
                rec.pop("_patch", None)
                rec.pop("_patch_full", None)
                if not raw:
                    rec.update({"harness_score": round(hs, 2), "llm_parse_failed": True,
                                "unscored_reason": "评委三次都没按格式返回，本条不计入均分"})
                else:
                    llm = EBV.aggregate(raw, prof["dims"])
                    rec.update({"harness_score": round(hs, 2), "llm_scores": raw, "llm_score": round(llm, 1),
                                "llm_one_line": parsed.get("one_line", ""), "w_local": prof["local_weight"],
                                "w_llm": prof["llm_weight"], "judge_model": CB.EVAL_LLM,
                                "final_100": round(hs * prof["local_weight"] + llm * prof["llm_weight"], 1),
                                "judge_version": getattr(CB, "JUDGE_VERSION", "v2_20261008" if getattr(CB, "JUDGE_V2", False) else "v1"),  # 10-09：跟 claw_batch 的评委版本走（v2.1）
                                "judge_input_v2": rec.get("judge_input_v2")})
        if g["verdict"] == "uncertain":
            rec["leak_gate_pending_review"] = True
    rec["done"] = True
    out_f.write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    # 退役旧污染记录（移档，不删）
    ARCH.mkdir(exist_ok=True)
    for f in pl["old_files"]:
        src = TAX / f
        if src.exists():
            shutil.move(str(src), str(ARCH / f))
    # 腾盘：链里的依赖目录删掉（会话记录与补丁留着）
    sh(f"sudo -n rm -rf '{SB.chain_dir(chain)}/home/.rustup' '{SB.chain_dir(chain)}/home/.cargo/registry' "
       f"'{SB.chain_dir(chain)}/home/go' '{ws}/node_modules' '{ws}/vendor' '{SB.chain_dir(chain)}/home/.bundle-gems'")
    log(f"  ★ {model} {task}: gate={g['verdict']} harness={rec.get('harness_score')} judge={rec.get('llm_score')} "
        f"final={rec.get('final_100')} or=${rec.get('or_spend_usd')} cc=${rec.get('cost_usd_cc_reported')} el={el}s")
    return rec


def disk_pct():
    u = shutil.disk_usage("/")
    return 100.0 * u.used / u.total


# crc 22:40（审计建议 4）：git add -A 不再把缓存/构建产物收进交付补丁。只排除缓存类，不排除 lockfile
#   （改 lockfile 可能是正当的加依赖；评委 v2 的视图里 lockfile 另行折叠）。被排除的路径和大小记在 artifacts_excluded。
CACHE_RE = re.compile(r"(^|/)(node_modules|\.phpunit\.cache|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|\.tox"
                      r"|\.nyc_output|\.cache|\.gradle|\.sass-cache|\.jekyll-cache|\.bundle|target)/"
                      r"|\.phpunit\.result\.cache$|\.pyc$|\.class$|\.o$|\.DS_Store$")


def exclude_artifacts(ws, base, patch):
    names = sh("git diff --cached --name-only", cwd=str(ws)).stdout.split("\n")
    bad = [n for n in names if n and CACHE_RE.search(n)]
    if not bad:
        return patch, []
    sizes = {}
    for blk in re.split(r"(?m)^(?=diff --git )", patch):
        m = re.match(r"diff --git a/(\S+) b/(\S+)", blk)
        if m and m.group(2) in bad:
            sizes[m.group(2)] = len(blk)
    for i in range(0, len(bad), 200):
        subprocess.run(["git", "reset", "-q", "--", *bad[i:i + 200]], cwd=str(ws))
    patch = sh(f"git diff --cached {base}", cwd=str(ws)).stdout or ""
    return patch, [{"path": b, "chars": sizes.get(b)} for b in bad][:200]


def drop_eval_image(task):
    """腾盘：只删本题的评测镜像（swebench/sweb.eval.x86_64.<id>），下一个模型批再拉。"""
    img = "swebench/sweb.eval.x86_64." + task.replace("__", "_1776_").lower() + ":latest"
    r = sh(f"docker rmi {img}", timeout=600)
    log(f"  rmi {img} rc={r.returncode}")


def annotate_gate(rec):
    """顶层摘要：精确闸门判定 + 证据（main 21:3x 要求每条 __iso 都写明）。沙箱扫描的 hard 命中在断网下只是「尝试」。"""
    g = rec.get("leak_gate") or {}
    hard = (rec.get("leak_scan_sandbox") or {}).get("hard") or []
    rec["gate"] = "precise_gate"
    rec["leak_verdict"] = g.get("verdict")
    rec["contaminated"] = g.get("verdict") == "contaminated"
    rec["leak_evidence"] = {"hits_by_source": g.get("hits"), "n_strong": g.get("n_strong"), "thr": g.get("thr"),
                            "n_dist": g.get("n_dist"), "applied_ext": g.get("applied_ext"), "reasons": g.get("reasons"),
                            "evidence": g.get("evidence"), "session": g.get("session_file")}
    rec["net_attempts_blocked"] = [f"{h.get('kind')}: {h.get('what')} | {str(h.get('snippet'))[:160]}" for h in hard][:10]
    return rec


def load_ok():
    return os.getloadavg()[0] < 4.0


def batch(model, limit=999, conc=2, only=None):
    import claw_batch as CB
    _jv = os.environ.get("CLAW_EXPECT_JUDGE", "v2.1_20261009")   # 10-09 main：新进程开跑前必须是评委 v2.1
    assert CB.JUDGE_VERSION == _jv, f"claw_batch 评委版本是 {CB.JUDGE_VERSION}，不是 {_jv}，拒绝开跑"
    todo = [p for p in plan() if p["model"] == model and p["task"] not in PYTHON_HOLD and (not only or p["task"] in only)]
    todo = [p for p in todo if not (TAX / f"claw_run_{model.replace('/', '_')}__{p['task']}__iso.json").exists()]
    todo.sort(key=lambda p: PRIORITY.index(p["task"]) if p["task"] in PRIORITY else 100)
    todo = todo[:limit]
    log(f"batch {model}: {len(todo)} 对，并发 {conc}")
    q = list(todo)
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            if (HERE / "STOP").exists():
                log("STOP 文件在，不再开新的")
                return
            with _lock:
                if not q:
                    return
                p = q.pop(0)
            while not load_ok():
                time.sleep(60)
            if disk_pct() >= 93:
                log(f"⛔ 磁盘 {disk_pct():.1f}% >= 93%，停")
                stop.set()
                return
            try:
                run_pair(model, p["task"])
            except CB.QuotaWall as e:
                log(f"⛔ 额度墙：{e}")
                stop.set()
            except SystemExit as e:
                log(f"⛔ 停：{e}")
                stop.set()
                with _lock:
                    q.insert(0, p)
            except Exception as e:  # noqa: BLE001
                import traceback
                log(f"  ❌ {p['task']} {type(e).__name__}: {e} {traceback.format_exc()[-600:]}")
            time.sleep(20)
    ths = [threading.Thread(target=worker) for _ in range(conc)]
    for i, t in enumerate(ths):
        t.start()
        time.sleep(90 if i == 0 else 0)
    for t in ths:
        t.join()
    left = [p["task"] for p in todo if not (TAX / f"claw_run_{model.replace('/', '_')}__{p['task']}__iso.json").exists()]
    log(f"batch {model} 结束；未完成 {len(left)} 对：{left}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "tpl":
        for t in a[1:]:
            try:
                make_tpl(t)
            except Exception as e:  # noqa: BLE001
                log(f"[tpl] {t} ❌ {e}")
    elif a[0] == "smoke":
        for t in a[1:]:
            smoke(t)
    elif a[0] == "run":
        print(json.dumps(run_pair(a[1], a[2]), ensure_ascii=False)[:2000])
    elif a[0] == "batch":
        batch(a[1], int(a[2]) if len(a) > 2 else 999, only=set(a[3].split(",")) if len(a) > 3 else None)
