import json,glob,os,re,sys
rows=[]
TEST=re.compile(r"(pytest|go test|mvn |gradle|npm (run )?test|yarn test|cargo test|phpunit|rspec|jest|vitest|make test|ctest|tox|unittest|bundle exec rake|rake test|composer test|\./vendor/bin|npx |node .*test)",re.I)
for rec in glob.glob('traj/traj_export/*/dsh_r*/record.json'):
    d=os.path.dirname(rec); r=json.load(open(rec)); t=r['task']
    if not os.path.exists(d+'/session.jsonl'): continue
    steps=[]
    for line in open(d+'/session.jsonl'):
        try: o=json.loads(line)
        except Exception: continue
        m=o.get('message') or {}
        if o.get('type')=='assistant' and isinstance(m.get('content'),list):
            for b in m['content']:
                if b.get('type')=='tool_use': steps.append((b.get('name',''),json.dumps(b.get('input',{}),ensure_ascii=False)))
    n=len(steps)
    if n==0: continue
    names=[s[0] for s in steps]
    isedit=[nm in('Edit','Write','MultiEdit','NotebookEdit') for nm in names]
    first_edit=next((i for i,e in enumerate(isedit) if e),None)
    bash=[s[1] for s in steps if s[0]=='Bash']
    testrun=[i for i,s in enumerate(steps) if s[0]=='Bash' and TEST.search(s[1])]
    editpaths=[re.search(r'"(?:file_path|path)":\s*"([^"]+)"',s[1]).group(1) for s in steps if s[0] in('Edit','Write','MultiEdit') and re.search(r'"(?:file_path|path)":\s*"([^"]+)"',s[1])]
    testedit=[p for p in editpaths if re.search(r'(test|spec|_test\.|Test)',p)]
    search=[i for i,s in enumerate(steps) if s[0] in('Grep','Glob') or (s[0]=='Bash' and re.search(r'\b(grep|rg|find|ag)\b',s[1]))]
    reads=[i for i,s in enumerate(steps) if s[0]=='Read']
    post_edit_search=[i for i in search if first_edit is not None and i>first_edit]
    rows.append(dict(task=t,rep=r['rep'],resolved=r['resolved'],turns=r.get('turns'),n_tool=n,n_edit=sum(isedit),n_files=len(set(editpaths)),n_testfile_edit=len(set(testedit)),
        n_testrun=len(testrun),first_edit_frac=(first_edit/n) if first_edit is not None else 1.0,n_search=len(search),n_read=len(reads),n_search_after_edit=len(post_edit_search),
        last_is_test=int(bool(testrun) and testrun[-1]>=n-4),elapsed=r.get('elapsed_s'),cost=r.get('cost_token_est_usd'),empty=int(sum(isedit)==0)))
json.dump(rows,open('traj/features.json','w')); print(len(rows),'条轨迹特征')
