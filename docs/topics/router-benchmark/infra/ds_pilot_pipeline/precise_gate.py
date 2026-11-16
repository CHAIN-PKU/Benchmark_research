# rb 11-13 23:3x：APPLY 不再把 git merge-base（只读查询）当成打补丁；ref_state 改查本次运行的工作区（修 jekyll-8771 误判：过去的提交被当成未来）
# rb 复制自 ai-market/scratchpad/claw_leak_20261008/precise_gate.py（2026-11-13），只改了题库路径
"""claw 精确闸门 · 全量扫描（held-out + 非 held-out），$0、只读会话记录。

相对 fecell_gate_all.py（近似版）的改动：
  1. 特征行按 **base 版本的被改文件** 过滤（prep_distinct.py；近似版只用了补丁上下文行）。
  2. **起始版本过滤**：git 命令里出现的 ref/sha 逐个在上游 clone 里解析，凡是 base 本身或 base 的祖先
     （merge-base --is-ancestor）都算"过去的历史"，这条命令返回的东西不计入命中。
     --all/--branches/--remotes/--tags/FETCH_HEAD、解析不到的 sha、不是 base 祖先的 ref → 未来历史。
  3. **自己写的不算**：命中行如果在此前任何一次工具调用的输入里（Edit/Write/Bash 命令正文…）出现过，
     说明是 agent 自己写的，不计入命中（近似版会把 `cat /tmp/my.patch` 当成泄漏）。
  4. `git apply /tmp/x.patch` 只有当 x.patch 是联网/未来历史命令产出的才算"直接打上游补丁"。
  5. 三态：contaminated / clean / uncertain，并写明理由。
来源分类：net（curl/wget/git fetch/gh api/pip download/…）、future（未来历史）、ext（读工作区以外的文件，
如 /tmp 下载物、包缓存）、local（工作区内读写、git diff 等，不计入）、past（base 祖先，不计入）。
"""
import json, re, subprocess, pathlib, glob, collections, functools, sys, os
H = pathlib.Path("/home/ubuntu/ai-market/scratchpad/claw_leak_20261008")   # rb: 数据文件仍读老目录（只读）
TAX = pathlib.Path("/home/ubuntu/ai-market/data/cold_start/taxonomy")
DL = json.loads((H / "distinct_lines.json").read_text())
rows = {json.loads(l)["instance_id"]: json.loads(l) for l in open("/home/ubuntu/benchmark_router_paper/claude_eval/claw_restore/bench-probe/vendor/claw-swe-bench/full-test.jsonl")}
PROJ = pathlib.Path.home() / ".claude/projects"

def norm(s): return re.sub(r"\s+", " ", s or "").strip()

NET = re.compile(r"\bcurl\b|\bwget\b|git (fetch|ls-remote|clone|pull)\b|\bgh (api|pr|repo|release)\b|urllib|requests\.(get|post)"
                 r"|raw\.githubusercontent|pip3? (download|install)|npm (view|pack|install)|go (get|mod download)|cargo (add|update|install|search)"
                 r"|composer (require|update|install)|gem (fetch|install)|bundle (install|update)")
FIXURL = re.compile(r"(pull|pulls)/\d+|/commits?/[0-9a-f]{7}|/files\b|\.(diff|patch)\b|compare/|refs/pull|archive/|zipball|tarball|gh pr diff")
EXTPATH = re.compile(r"(?<![\w.])(/tmp\b|/root/|~/|/home/ubuntu/(?!swebp/clawrun)|\.cargo/registry|go/pkg/mod|site-packages|\.m2/repository|vendor/bundle|\.gem/)")
FUT_FLAG = re.compile(r"--all\b|--branches|--remotes|--tags\b|FETCH_HEAD|refs/pull|origin/|upstream/")
GITCMD = re.compile(r"\bgit\s+(?:-C\s+\S+\s+)?(show|log|diff|checkout|switch|cat-file|grep|ls-tree|blame|rev-list|reset|merge|cherry-pick|rebase|format-patch|archive|stash|whatchanged|describe|branch|tag|for-each-ref|name-rev|rev-parse|restore)\b")
APPLY = re.compile(r"git (apply|am|cherry-pick|merge(?!-))\b|patch -p\d|\bpatch\s+<")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
NAMEISH = re.compile(r"^(master|main|develop|dev|trunk|HEAD@\{.*\}|v?\d+\.\d+(\.\d+)?[\w.-]*|\d+\.x|[0-9]+\.[0-9]+-stable|stable|release[\w./-]*)$")

_WS_GIT = None   # rb 11-13：老的上游镜像目录已归档；改查本次运行的工作区（只留了 base 及以前的历史）


@functools.lru_cache(maxsize=None)
def ref_state(repo, base, tok):
    """'past'（base 或其祖先）/'future'/'unknown'"""
    g = _WS_GIT if _WS_GIT and os.path.isdir(_WS_GIT) else str(H / "repos" / (repo.replace("/", "_") + ".git"))
    p = subprocess.run(["git", "-C", g, "rev-parse", "--verify", "-q", tok + "^{commit}"], capture_output=True, text=True)
    if p.returncode:
        return "unknown"
    sha = p.stdout.strip()
    if sha.startswith(base[:len(sha)]) or base.startswith(sha):
        return "past"
    a = subprocess.run(["git", "-C", g, "merge-base", "--is-ancestor", sha, base])
    return "past" if a.returncode == 0 else "future"

def classify_git(cmd, repo, base, fut_names=()):
    """git 命令的历史时态：'future' / 'past' / 'local'，以及引用到的未来 ref。"""
    if not GITCMD.search(cmd) and "git " not in cmd:
        return "local", []
    if FUT_FLAG.search(cmd):
        return "future", [FUT_FLAG.search(cmd).group(0)]
    segs = re.split(r"[;&|]+", cmd)
    fut, past = [], []
    for s in segs:
        if not GITCMD.search(s):
            continue
        for raw in s.split():
            tok = raw.strip("'\"()")
            if tok.startswith("-") or "=" in tok:
                continue
            for part in re.split(r"\.\.\.?", tok):
                part = re.sub(r"[\^~]\d*$", "", part.split(":")[0])
                if not part or part in ("git", "HEAD"):
                    continue
                if part in fut_names:
                    fut.append(part); continue
                if SHA.match(part) or NAMEISH.match(part):
                    st = ref_state(repo, base, part)
                    if st == "future" or (st == "unknown" and SHA.match(part) and len(part) >= 7 and not part.isdigit()):
                        fut.append(part)
                    elif st == "past":
                        past.append(part)
    if fut:
        return "future", fut
    if past:
        return "past", past
    return "local", []

def result_text(cc):
    if isinstance(cc, str):
        return cc
    if isinstance(cc, list):
        return "\n".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in cc)
    return json.dumps(cc, ensure_ascii=False)

def load_session(f):
    ev = []  # (kind, id, payload) in order
    final = ""; ts = []
    files = [f] + sorted((f.parent / f.stem / "subagents").glob("*.jsonl")) if (f.parent / f.stem / "subagents").is_dir() else [f]
    for ff in files:
        for line in open(ff, errors="replace"):
            try:
                j = json.loads(line)
            except Exception:
                continue
            if ff == f and j.get("timestamp"):
                ts.append(j["timestamp"])
            msg = j.get("message") or {}
            c = msg.get("content")
            if not isinstance(c, list):
                continue
            for x in c:
                if not isinstance(x, dict):
                    continue
                if x.get("type") == "tool_use":
                    ev.append(("use", x.get("id"), x))
                elif x.get("type") == "tool_result":
                    ev.append(("res", x.get("tool_use_id"), result_text(x.get("content"))))
            if ff == f and msg.get("role") == "assistant":
                tx = [x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text"]
                if tx and tx[-1].strip():
                    final = tx[-1]
    import datetime as _dt
    dur = None
    if ts:
        p = lambda s: _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        dur = (p(max(ts)) - p(min(ts))).total_seconds()
    return ev, final, dur

def use_text(u):
    inp = u.get("input") if isinstance(u.get("input"), dict) else {}
    return json.dumps(inp, ensure_ascii=False).replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")

def scan(f, task, wd_hint):
    global _WS_GIT
    _m = re.search(r"(/home/coder/chains/[^/]+)/", str(f))
    _WS_GIT = (_m.group(1) + "/ws") if _m else None
    info = DL[task] if task in DL else _rb_distinct(task); repo, base = info["repo"], info["base"]
    dist = info["distinct"]; relaxed = False
    if not dist:  # 0 条特征行的题：放宽到 ≥12 字符（只作参考，命中也只判 uncertain）
        r = rows[task]
        g = {norm(x[1:]) for x in r["patch"].splitlines() if x.startswith("+") and not x.startswith("+++")}
        ctx = {norm(x[1:]) for x in r["patch"].splitlines() if x[:1] in (" ", "-")}
        dist = sorted(x for x in g if len(x) >= 12 and x not in ctx and x not in norm(r["problem_statement"]))
        relaxed = True
    thr = min(3, len(dist)) if dist else 99
    ev, final, dur = load_session(f)
    uses = {}
    authored = ""  # 此前所有工具调用输入的拼接（已规范化）
    hits = collections.defaultdict(set)  # src -> lines
    evid = collections.defaultdict(list)
    produced_paths = set()  # 联网/未来历史命令产出的文件
    applied_ext = []
    fut_cmds = []; net_fix_cmds = []; fut_names = set(); acq_seen = [False]
    for kind, i, x in ev:
        if kind == "use":
            uses[i] = x
            t = use_text(x)
            if x.get("name") == "Bash":
                cmd = (x.get("input") or {}).get("command", "") or ""
                src = "local"
                if NET.search(cmd):
                    src = "net"
                if re.search(r"git fetch", cmd):
                    fut_names |= set(re.findall(r":(?:refs/heads/)?([\w./-]+)", cmd.split("git fetch", 1)[1].split("&&")[0]))
                for a, b in re.findall(r"git (?:checkout -b|switch -c|branch)\s+([\w./-]+)\s+([\w./-]+)", cmd):
                    if b in fut_names or b.startswith("origin/") or b == "FETCH_HEAD":
                        fut_names.add(a)
                tense, refs = classify_git(cmd, repo, base, fut_names)
                if tense == "future":
                    src = "future" if src != "net" else "net"
                    fut_cmds.append(cmd[:160])
                if src in ("net", "future"):
                    for pth in re.findall(r"(?:-o\s*|>\s*|--output[= ])(\S+)", cmd):
                        produced_paths.add(pth.strip("'\""))
                    num = info["repo"].split("/")[1]
                    short = repo.split("/")[1].lower()
                    if src == "net" and FIXURL.search(cmd) and short in cmd.lower() and not re.match(r"\s*(cat|python3?|tee)\b[^\n]*<<", cmd):
                        net_fix_cmds.append(cmd[:160])
                    acq_seen[0] = True
                if APPLY.search(cmd):
                    if re.search(r"FETCH_HEAD|origin/|curl|wget", cmd) or any(p and p in cmd for p in produced_paths) or tense == "future":
                        applied_ext.append(cmd[:160])
                if src == "local" and EXTPATH.search(cmd):
                    src = "ext"
                if src == "local" and acq_seen[0]:
                    src = "local_after_acq"
                x["_src"] = src
            elif x.get("name") in ("Read", "Grep", "Glob", "NotebookRead"):
                inp = x.get("input") or {}
                pth = str(inp.get("file_path") or inp.get("path") or "")
                x["_src"] = "ext" if pth and wd_hint and not pth.startswith(wd_hint) else ("local_after_acq" if acq_seen[0] else "local")
            else:
                x["_src"] = "local"
            authored += "\n" + norm(t)
        else:
            u = uses.get(i)
            if not u:
                continue
            src = u.get("_src", "local")
            rn = norm(re.sub(r"(?m)^\s*\d+[→\t]", "", x.replace("\\n", "\n").replace('\\"', '"').replace("\\t", "\t")))
            h = {g for g in dist if g in rn and g not in authored}
            if h:
                if src == "ext" and any(p in str((u.get("input") or {}).get("file_path", "")) for p in ("/tmp/claw_pred",)):
                    src = "local"
                new = h - hits[src]
                hits[src] |= h
                if new:
                    s = (u.get("input") or {}).get("command") or (u.get("input") or {}).get("file_path") or u.get("name")
                    evid[src].append(f"{str(s)[:140]} [+{len(new)}]")
    strong = hits["net"] | hits["future"] | hits["ext"]
    netfut = hits["net"] | hits["future"]
    n_strong = len(strong); n_local = len(hits["local"] - strong)
    n_after = len(hits["local_after_acq"] - strong)
    reasons = []
    small = len(dist) <= 2   # 特征行 ≤2 条的题：单行命中太脆，只认联网/未来历史来源
    if relaxed:
        reasons.append(f"本题严格特征行为 0，放宽到 ≥12 字符共 {len(dist)} 条")
    if applied_ext:
        verdict = "contaminated"
    elif (len(netfut) >= thr) if (small or relaxed) else (n_strong >= thr):
        verdict = "contaminated"
    elif n_strong > 0 or (n_strong + n_after) >= thr:
        verdict = "uncertain"
        if n_after: reasons.append(f"拿过外部材料之后，工作区里出现 {n_after} 条非自己写的特征行（可能是拷进来/打进来的）")
    else:
        verdict = "clean"
    if applied_ext: reasons.append("直接打上游补丁：" + applied_ext[0])
    if n_strong: reasons.append(f"联网/未来历史/外部文件返回里命中特征行 {n_strong}/{len(dist)}（门槛 {thr}）")
    if net_fix_cmds and verdict != "contaminated": reasons.append("请求过上游 PR 补丁/commit/compare（尝试过；返回里特征行不足门槛）：" + net_fix_cmds[0])
    return {"verdict": verdict, "session": f.name[:8], "final": final, "dur": dur, "n_dist": len(dist), "thr": thr,
            "hits": {k: len(v) for k, v in hits.items() if v}, "n_strong": n_strong, "attempted": bool(net_fix_cmds), "n_local_only": n_local,
            "applied_ext": applied_ext[:2], "net_fix_cmds": net_fix_cmds[:3], "future_cmds": fut_cmds[:3],
            "evidence": {k: v[:3] for k, v in evid.items()}, "reasons": reasons, "relaxed": relaxed}

# rb 11-14：老 distinct_lines.json 只覆盖老流水线跑过的题；新题按 prep_distinct.py 同样的规则现算
# （基线文件内容取自本次运行工作区里的 base 提交），结果缓存到本目录 distinct_lines_rb.json，不改老文件。
_RB_DL_PATH = pathlib.Path(__file__).resolve().parent / "distinct_lines_rb.json"
def _rb_distinct(task):
    cache = json.loads(_RB_DL_PATH.read_text()) if _RB_DL_PATH.exists() else {}
    if task in cache:
        return cache[task]
    r = rows[task]
    files = re.findall(r"^diff --git a/(\S+) b/", r["patch"], re.M)
    base_lines, missing = set(), []
    for f in files:
        q = subprocess.run(["git", "-C", str(_WS_GIT), "show", f"{r['base_commit']}:{f}"], capture_output=True, text=True, errors="replace")
        if q.returncode: missing.append(f)
        base_lines |= {norm(x) for x in q.stdout.splitlines()}
    ps = norm(r.get("problem_statement", ""))
    GEN = re.compile(r"(^|/)(parser|lexer)\.[ch]$|generated_parser\.y\.go$|\.pb\.go$|\.prebuilt$")
    parts = re.split(r"(?m)^diff --git a/(\S+) b/\S+\n", r["patch"])
    keep = "\n".join(parts[i + 1] for i in range(1, len(parts), 2) if not GEN.search(parts[i]))
    g = {norm(x[1:]) for x in keep.splitlines() if x.startswith("+") and not x.startswith("+++")}
    dist = sorted(x for x in g if len(x) >= 25 and x not in base_lines and x not in ps)
    info = {"repo": r["repo"], "base": r["base_commit"], "files": files, "new_files": missing, "distinct": dist,
            "source": "rb _rb_distinct (prep_distinct.py 同规则，基线取自运行工作区)"}
    cache[task] = info
    _RB_DL_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1))
    return info

def key(s): return re.sub(r"\s+", "", s or "")[:30]

def main():
    recs = []
    for p in sorted(TAX.glob("claw_run_*.json")):
        try:
            r = json.loads(p.read_text())
        except Exception:
            continue
        if isinstance(r, dict) and r.get("task_id") in DL:
            recs.append((p.name, r))
    cache = {}
    out = []
    for name, r in recs:
        t, m = r["task_id"], r.get("model", "")
        wd = r.get("workdir") or f"/home/ubuntu/swebp/clawrun/{m.replace('/', '_')}__{t}"
        slug = re.sub(r"[/_.]", "-", wd)
        d = PROJ / slug
        fs = sorted(d.glob("*.jsonl")) if d.is_dir() else []
        if r.get("session_id") and (d / f"{r['session_id']}.jsonl").is_file():
            fs = [d / f"{r['session_id']}.jsonl"]
        cands = []
        for f in fs:
            if f not in cache:
                cache[f] = scan(f, t, wd)
            cands.append(cache[f])
        rh = key(r.get("result_head"))
        match = [c for c in cands if rh and key(c["final"]) == rh]
        el = r.get("elapsed_s")
        def close(c):
            return el and c.get("dur") is not None and abs(c["dur"] - el) <= max(60, 0.15 * el)
        if len(match) > 1 and el:   # 撞额度墙/同样收尾的多个会话：用墙钟时长消歧
            m2 = [c for c in match if close(c)]
            if len(m2) == 1:
                match = m2
        if not match and el:
            m2 = [c for c in cands if close(c)]
            if len(m2) == 1:
                match = m2
        fresh = "__fresh" in name
        base = dict(file=name, task=t, model=m, heldout=fresh, harness=r.get("harness_score"), final_100=r.get("final_100"))
        if len(match) >= 1:
            vs = {c["verdict"] for c in match}
            if len(vs) == 1:
                c = match[0]; v = c["verdict"]
            else:
                c = max(match, key=lambda c: ["clean", "uncertain", "contaminated"].index(c["verdict"])); v = "uncertain"
                c = dict(c, reasons=c["reasons"] + [f"result_head 对上 {len(match)} 个会话、判定不一致"])
            base.update(verdict=v, match="exact", **{k: c[k] for k in ("session", "n_dist", "thr", "hits", "n_strong", "attempted", "applied_ext", "net_fix_cmds", "future_cmds", "evidence", "reasons", "relaxed")})
        elif cands:
            worst = max(cands, key=lambda c: ["clean", "uncertain", "contaminated"].index(c["verdict"]))
            if worst["verdict"] == "clean":
                v = "clean"; rs = [f"会话没精确对上，但同目录 {len(cands)} 个会话全部干净"]
            else:
                v = "uncertain"; rs = [f"会话没精确对上；同目录 {len(cands)} 个会话里有判 {worst['verdict']} 的（{worst['session']}）"] + worst["reasons"]
            base.update(verdict=v, match="unmatched", session=None, reasons=rs, n_dist=worst["n_dist"], hits=worst["hits"], evidence=worst["evidence"])
        else:
            base.update(verdict="uncertain", match="no_session", reasons=["找不到会话记录（找不到 ≠ 干净）"])
        out.append(base)
    (H / "precise_gate.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    C = collections.Counter((o["heldout"], o["verdict"]) for o in out)
    for k, v in sorted(C.items()): print(k, v)

if __name__ == "__main__":
    main()
