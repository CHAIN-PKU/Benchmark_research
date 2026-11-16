import pathlib, re, shutil, subprocess
D=pathlib.Path("/home/ubuntu/benchmark_router_paper/claude_eval/ds_pilot")
ps=subprocess.run("ps -eo args | grep 'ds_pilot.py run' | grep -v grep",shell=True,capture_output=True,text=True).stdout
running={t for t,r in re.findall(r"ds_pilot\.py run (\S+) (\d+)",ps)}
freed=0; removed=[]
for d in (D/"tpl").iterdir():
    if not d.is_dir(): continue
    t=d.name
    if t in running: continue
    r1=(D/"runs"/t/"dsh_r1"/"record.json").exists()
    r2=(D/"runs"/t/"dsh_r2"/"record.json").exists()
    if r1 and not r2:
        try: sz=sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        except: sz=0
        shutil.rmtree(d, ignore_errors=True); freed+=sz; removed.append(t)
print("removed",len(removed),"freed_gb",round(freed/1e9,2))
