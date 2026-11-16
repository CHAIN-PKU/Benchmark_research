"""给早期记录补字段（不改原 record.json，写 BACKFILL.json）：按用量折算成本、事后补查的镜像指纹（Hub 网页接口，不计下载次数）。"""
import json, glob, sys, time, urllib.request
sys.argv = ["x"]; sys.path.insert(0, ".")
import ds_pilot as P
for f in sorted(glob.glob("runs/*/ds_r*/record.json")):
    d = json.load(open(f)); od = f.rsplit("/", 1)[0]; bf = {}
    if d.get("cost_token_est_usd") is None:
        bf["cost_token_est_usd"] = P.token_est(d.get("usage") or {})
        bf["cost_note"] = "按记录里的 usage 事后折算（cost_lib 口径）"
    e = d.get("eval") or {}
    if "sha256" not in str(e.get("image_repo_digests")):
        repo = "sweb.eval.x86_64." + d["task"].replace("__", "_1776_")
        j = json.load(urllib.request.urlopen(f"https://hub.docker.com/v2/repositories/swebench/{repo}/tags/latest", timeout=30))
        bf["image_digest_backfilled"] = [i["digest"] for i in j.get("images", []) if i.get("architecture") == "amd64"] or j.get("digest")
        bf["image_last_pushed"] = j.get("tag_last_pushed")
        bf["digest_note"] = "评测时没记；事后从 Docker Hub 查 latest 的指纹。若镜像在评测后更新过（看 image_last_pushed），则不保证是评测用的那份"
    if bf:
        bf["at"] = time.strftime("%F %T")
        json.dump(bf, open(od + "/BACKFILL.json", "w"), ensure_ascii=False, indent=1)
        print(f.split("/")[1], d["rep"], {k: v for k, v in bf.items() if k in ("cost_token_est_usd", "image_last_pushed")})
