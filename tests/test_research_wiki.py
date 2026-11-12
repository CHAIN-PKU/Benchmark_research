import importlib.util
import json
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / ".claude/skills/research-wiki/scripts/wiki.py"
spec = importlib.util.spec_from_file_location("wiki", SCRIPT)
wiki = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wiki)


def run(root, *args):
    return wiki.main(["--root", str(root), *args])


@pytest.fixture
def root(tmp_path):
    assert run(tmp_path, "init") == 0
    return tmp_path


def test_missing_root_fails_loudly(monkeypatch, capsys):
    monkeypatch.delenv("RESEARCH_WIKI_DIR", raising=False)
    assert wiki.main(["lint"]) == 2
    assert "RESEARCH_WIKI_DIR" in capsys.readouterr().err


def test_uninitialised_root_fails(tmp_path, capsys):
    assert run(tmp_path, "lint") == 2
    assert "init" in capsys.readouterr().err


def test_init_keeps_existing_content(root):
    (root / "log.md").write_text("keep me\n", encoding="utf-8")
    assert run(root, "init") == 0
    assert (root / "log.md").read_text(encoding="utf-8") == "keep me\n"


def test_new_creates_page_and_refuses_duplicate(root, capsys):
    assert run(root, "new", "experiment", "lr-sweep", "学习率扫描") == 0
    page = root / "experiments/lr-sweep.md"
    assert page.read_text(encoding="utf-8").startswith("# 学习率扫描")
    assert run(root, "new", "experiment", "lr-sweep", "again") == 2
    assert "已存在" in capsys.readouterr().err


def test_new_rejects_bad_slug(root):
    assert run(root, "new", "idea", "../escape", "x") == 2
    assert not (root.parent / "escape.md").exists()


def test_link_validates_and_dedupes(root, capsys):
    run(root, "new", "idea", "warmup", "加 warmup 能稳住训练")
    run(root, "new", "experiment", "warmup-run", "warmup 对照实验")
    assert run(root, "link", "idea:warmup", "tested_by", "experiment:warmup-run") == 0
    assert run(root, "link", "idea:warmup", "tested_by", "experiment:warmup-run") == 0
    edges = (root / "graph/edges.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(edges) == 1
    assert run(root, "link", "idea:warmup", "likes", "experiment:warmup-run") == 2
    assert run(root, "link", "idea:warmup", "tested_by", "experiment:missing") == 2
    assert run(root, "link", "idea:warmup", "related", "idea:warmup") == 2


def test_show_lists_both_directions(root, capsys):
    run(root, "new", "idea", "warmup", "加 warmup")
    run(root, "new", "experiment", "warmup-run", "对照实验")
    run(root, "link", "experiment:warmup-run", "supports", "idea:warmup", "--note", "loss 不再发散")
    capsys.readouterr()
    assert run(root, "show", "idea:warmup") == 0
    out = capsys.readouterr().out
    assert "← supports experiment:warmup-run（loss 不再发散）" in out


def test_search_long_and_short_chinese_terms(root, capsys):
    run(root, "new", "experience", "feishu-id", "飞书消息 id 不能猜")
    (root / "experiences/feishu-id.md").write_text(
        "# 飞书消息 id 不能猜\n\n## 现象\n调用回复接口返回 400 invalid message_id\n", encoding="utf-8")
    run(root, "new", "paper", "trak", "TRAK 数据归因")
    capsys.readouterr()
    assert run(root, "search", "message_id") == 0
    out = capsys.readouterr().out
    assert "experience:feishu-id" in out and "paper:trak" not in out
    assert run(root, "search", "飞书") == 0
    out = capsys.readouterr().out
    assert "子串匹配" in out and "experience:feishu-id" in out
    assert run(root, "search", "完全不存在的词") == 0
    assert "没有命中" in capsys.readouterr().out


def test_lint_catches_broken_graph(root, capsys):
    run(root, "new", "claim", "c1", "论断一")
    with open(root / "graph/edges.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"from": "claim:c1", "rel": "supports", "to": "idea:gone"}) + "\n")
        f.write(json.dumps({"from": "claim:c1", "rel": "bogus", "to": "claim:c1"}) + "\n")
    assert run(root, "lint") == 1
    out = capsys.readouterr().out
    assert "idea:gone" in out and "未知关系" in out


def test_index_lists_nodes_with_degree(root):
    run(root, "new", "idea", "a", "想法 A")
    run(root, "new", "claim", "b", "论断 B")
    run(root, "link", "idea:a", "related", "claim:b")
    assert run(root, "index") == 0
    text = (root / "index.md").read_text(encoding="utf-8")
    assert "[想法 A](ideas/a.md) `idea:a` · 1 条关系" in text
