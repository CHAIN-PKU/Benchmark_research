#!/usr/bin/env python3
"""本地 CI：push 和开 PR 之前必须全绿。只用 Python 标准库，几秒内跑完。

用法：python3 ci/run.py        （在仓库根目录运行；任何一项失败，退出码为 1）

检查的都是这个仓库里真实会发生的问题：
  1. 密钥泄露：公开仓库，而 agent 手里有 GitHub / 飞书 / 模型 API 的凭证
  2. 大文件：误提交数据集或日志
  3. SKILL.md 格式：插件技能文件缺 name / description 就加载不了
  4. Python 语法：.py 文件至少要能编译
  5. 单元测试：仓库里有 tests/ 就跑 pytest；没装 pytest 直接报错，不跳过
"""
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
MAX_BYTES = 5 * 1024 * 1024

SECRET_PATTERNS = {
    "GitHub 令牌": re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"),
    "OpenAI/DeepSeek 类 API key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "AWS key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "私钥": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "写死的密钥": re.compile(
        r"(?i)(secret|token|password|api_key|apikey)[\"']?\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']"),
}


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True,
                         capture_output=True).stdout.decode()
    return [ROOT / p for p in out.split("\0") if p and (ROOT / p).is_file()]


def check_secrets(files):
    errors = []
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # 二进制文件交给大文件检查
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pat in SECRET_PATTERNS.items():
                if pat.search(line):
                    errors.append(f"{f.relative_to(ROOT)}:{lineno} 疑似{label}")
    return errors


def check_large(files):
    return [f"{f.relative_to(ROOT)} 有 {f.stat().st_size / 1e6:.1f} MB，超过 5 MB"
            for f in files if f.stat().st_size > MAX_BYTES]


def check_skills(files):
    errors = []
    for f in files:
        if f.name != "SKILL.md":
            continue
        text = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            errors.append(f"{f.relative_to(ROOT)} 开头没有 --- 包起来的 frontmatter")
            continue
        for key in ("name", "description"):
            if not re.search(rf"^{key}:", m.group(1), re.M):
                errors.append(f"{f.relative_to(ROOT)} frontmatter 缺 {key}")
    return errors


def check_python(files):
    errors = []
    for f in files:
        if f.suffix == ".py":
            try:
                compile(f.read_text(encoding="utf-8"), str(f), "exec")
            except SyntaxError as e:
                errors.append(f"{f.relative_to(ROOT)}:{e.lineno} 语法错误：{e.msg}")
    return errors


def check_tests(_files):
    if not (ROOT / "tests").is_dir():
        return []
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rfE", "tests"], cwd=ROOT)
    return [] if r.returncode == 0 else [f"pytest 失败（退出码 {r.returncode}）"]


CHECKS = [
    ("密钥泄露", check_secrets),
    ("大文件", check_large),
    ("SKILL.md 格式", check_skills),
    ("Python 语法", check_python),
    ("单元测试", check_tests),
]


def main():
    files = tracked_files()
    failed = False
    for name, fn in CHECKS:
        errors = fn(files)
        print(f"{'✅' if not errors else '❌'} {name}")
        for e in errors:
            print(f"    {e}")
        failed |= bool(errors)
    print("本地 CI：全绿，可以 push" if not failed else "本地 CI：有失败，先修再 push")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
