"""cucumber/godog 的官方评测适配层（Claude 版，2026-11-13）。

和 ops/adapters/godog_instance.py 的区别：
1. parse_log 真正解析 `go test -json` 输出（原版返回空结果，官方评测无法判分）。
2. 镜像里没有 /home/test.patch（SWE-bench-Live 镜像），测试补丁以 base64 形式写进评测命令，
   只在评测容器里还原；答题 agent 看不到它。
3. 待评补丁为空时跳过 git apply；补丁打不上则不跑测试（判为未解决）。
测试名格式与数据集一致：<包路径>::<测试名>（子测试带斜杠）。
"""
import base64
import json
from pathlib import Path

from multi_swe_bench.harness.image import Config, Image
from multi_swe_bench.harness.instance import Instance
from multi_swe_bench.harness.pull_request import PullRequest
from multi_swe_bench.harness.test_result import TestResult

IMAGE = "starryzhang/sweb.eval.x86_64.cucumber_1776_godog-695:latest"
SPEC = Path(__file__).resolve().parent / "godog_spec.json"   # 本地拷贝：只取 test_patch
GO = "/usr/local/go/bin/go"


def _test_patch_b64() -> str:
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    return base64.b64encode(spec["test_patch"].encode("utf-8")).decode("ascii")


class GodogImage(Image):
    def __init__(self, pr, config): self._pr = pr; self._config = config
    @property
    def pr(self): return self._pr
    @property
    def config(self): return self._config
    def dependency(self): return None
    def image_full_name(self): return IMAGE
    def image_name(self): return IMAGE.split(":")[0]
    def image_tag(self): return IMAGE.split(":")[-1]
    # 宿主机上存放日志的目录名；官方报告生成器只收集以 "pr-" 开头的目录
    def workdir(self): return f"pr-{self._pr.number}"
    def files(self): return []
    def dockerfile(self): return ""


@Instance.register("cucumber", "godog")
class GodogInstance(Instance):
    def __init__(self, pr: PullRequest, config: Config, *a, **k):
        self._pr = pr; self._config = config
    @property
    def pr(self): return self._pr
    def dependency(self): return GodogImage(self.pr, self._config)

    def _script(self, apply_fix: bool) -> str:
        steps = ["set -e", "cd /testbed",
                 f"echo {_test_patch_b64()} | base64 -d > /tmp/test.patch"]
        if apply_fix:
            steps.append("if [ -s /home/fix.patch ]; then git apply --whitespace=nowarn /home/fix.patch; "
                         "else echo 'EMPTY_FIX_PATCH'; fi")
        # 与官方 test_cmds 一致：主模块之外，_examples 是独立 Go 模块，也要跑。
        # 判分仍按冻结的 F2P/P2P 名单；_examples 的结果只做额外审计（见修正案草稿）。
        steps += ["git apply --whitespace=nowarn /tmp/test.patch", "set +e", f"{GO} test -v -json ./... 2>&1",
                  f"(cd _examples && {GO} test -v -json ./... 2>&1)", "exit 0"]
        return "; ".join(steps)

    def run(self): return ["bash", "-lc", f"cd /testbed && {GO} test -v -json ./... 2>&1; (cd _examples && {GO} test -v -json ./... 2>&1); exit 0"]
    def test_patch_run(self): return ["bash", "-lc", self._script(apply_fix=False)]
    def fix_patch_run(self, fix_patch_run_cmd: str = ""):
        return fix_patch_run_cmd or ["bash", "-lc", self._script(apply_fix=True)]

    def parse_log(self, test_log: str) -> TestResult:
        last = {}
        for line in test_log.splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("Test") and d.get("Action") in ("pass", "fail", "skip"):
                # _examples 是独立模块，冻结名单和前两段基线里都没有它；混进官方报告会被误算成「修好了」。
                # 这里不交给官方报告，单独由 audit_examples.py 对照基线审计（修正案 A12）。
                if "/_examples" in d.get("Package", ""):
                    continue
                last[f"{d.get('Package', '')}::{d['Test']}"] = d["Action"]
        passed = {k for k, v in last.items() if v == "pass"}
        failed = {k for k, v in last.items() if v == "fail"}
        skipped = {k for k, v in last.items() if v == "skip"}
        return TestResult(len(passed), len(failed), len(skipped), passed, failed, skipped)
