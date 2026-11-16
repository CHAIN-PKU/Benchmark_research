#!/usr/bin/env python3
"""每 10 分钟扫一遍新完成的运行：失败的自动查环境嫌疑，写 env_triage.log。
   环境嫌疑 = 会话里出现断网/装包失败/浏览器缺失等签名；供人工复核，不自动改判定。"""
import json, pathlib, re, time

HERE = pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot")
LOG = HERE/"env_triage.log"
MARK = HERE/".triage_mark"
SIG = re.compile(r"(EAI_AGAIN|ENOTFOUND|ECONNREFUSED|getaddrinfo|Could not find a version that satisfies|"
                 r"npm ERR!.*(network|ENOTFOUND|EAI_AGAIN)|No binary for Chrome|ChromeHeadless|"
                 r"karma.*(ERROR|error)|Failed to connect to|dial tcp.*(timeout|refused)|Cannot find module .formdata)",
                 re.I)

def main():
    since = 0.0
    if MARK.exists():
        try: since = float(MARK.read_text().strip())
        except Exception: since = 0.0
    now = time.time()
    new = []
    for t in sorted((HERE/"runs").iterdir()):
        if not t.is_dir(): continue
        for rep in sorted(t.glob("dsh_r*")):
            rp = rep/"record.json"
            if not rp.exists() or rp.stat().st_mtime <= since: continue
            try: d = json.loads(rp.read_text())
            except Exception: continue
            if d.get("resolved") is not False: continue
            hits = []
            for f in ("session.jsonl", "agent_stderr.txt"):
                p = rep/f
                if not p.exists(): continue
                try: txt = p.read_text(errors="ignore")
                except Exception: continue
                for m in SIG.finditer(txt):
                    hits.append(re.sub(r"\s+", " ", txt[max(0,m.start()-60):m.end()+60])[:180])
            if hits:
                new.append((t.name, rep.name, len(hits), hits[:2]))
    with open(LOG, "a", encoding="utf-8") as f:
        for name, rep, n, samples in new:
            f.write("%s FAIL %s %s hits=%d %s\n" % (time.strftime("%F %T"), name, rep, n, samples))
    MARK.write_text(str(now))
    if new:
        print("new env-suspect failures:", len(new))
        for x in new: print(x[0], x[1], x[2])

if __name__ == "__main__":
    main()
