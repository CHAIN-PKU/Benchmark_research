#!/bin/bash
# 在服务器上按基线提交重建代码快照（浅拉单个提交，删掉 .git，不含任何未来历史）
cd "$(dirname "$0")"; mkdir -p snap
python3 -c "import json;[print(t,v['repo'],v['base']) for t,v in json.load(open('repo_targets.json')).items()]" |
while read t repo sha; do
  [ -d snap/$t ] && continue
  tmp=snap/.tmp_$t; rm -rf $tmp; mkdir -p $tmp
  ( cd $tmp && git init -q && git remote add origin https://github.com/$repo.git &&
    timeout 900 git fetch -q --depth 1 origin $sha && git checkout -q FETCH_HEAD && rm -rf .git ) && mv $tmp snap/$t && echo "ok $t" || echo "FAIL $t"
done
ls snap | grep -v '^\.' | wc -l
