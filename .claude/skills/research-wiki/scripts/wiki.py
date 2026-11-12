#!/usr/bin/env python3
"""轻量研究 wiki：论文、想法、实验、论断、踩坑经验，各一页 Markdown，用一张关系图连起来。

参考 ARIS research-wiki（https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep ，MIT）改写：
保留「实体页 + 带类型的关系边」的思路，去掉对 Codex / arXiv 同步 / 其他 ARIS skill 的依赖，只用 Python 标准库。

数据目录由 --root 或环境变量 RESEARCH_WIKI_DIR 指定，两个都没有就报错退出（不猜默认位置）。

用法：
  wiki.py init
  wiki.py new <类型> <slug> "<标题>"         类型：paper / idea / experiment / claim / experience
  wiki.py link <源id> <关系> <目标id> [--note "说明"]
  wiki.py show <id>
  wiki.py search "<关键词>" [-k 10]
  wiki.py lint
  wiki.py index

节点 id 的写法是「类型:slug」，例如 experiment:2026-11-12-lr-sweep。slug 就是文件名（不含 .md）。
"""
import argparse
import datetime
import json
import os
import pathlib
import re
import sqlite3
import sys

TYPES = {
    "paper": "papers",
    "idea": "ideas",
    "experiment": "experiments",
    "claim": "claims",
    "experience": "experiences",
}

RELATIONS = {
    "extends": "在……基础上扩展",
    "contradicts": "与……结论矛盾",
    "supersedes": "取代了……",
    "inspired_by": "灵感来自……",
    "tested_by": "由……这个实验检验",
    "supports": "支持……",
    "invalidates": "推翻……",
    "learned_from": "这条经验来自……",
    "related": "相关",
}

TEMPLATES = {
    "paper": """# {title}

- 链接：
- 会议/年份：

## 一句话主张

## 解决什么问题

## 方法

## 关键结果

## 局限

## 对我们有用的点
""",
    "idea": """# {title}

- 日期：{date}
- 状态：提出 / 测试中 / 成立 / 失败

## 动机

## 假设

## 怎么验证

## 结果与原因
失败的想法也保留，写清楚为什么失败，避免以后重复尝试。
""",
    "experiment": """# {title}

- 日期：{date}
- 代码 commit：
- 运行环境：

## 假设
这个实验想验证什么。

## 设置
命令、数据、关键参数。

## 结果
贴数字，写原始日志或结果文件的路径。

## 结论
支持或推翻了哪个想法/论断（用 link 连上）。不确定就写「推断，待确认」。

## 下一步
""",
    "claim": """# {title}

- 状态：未验证 / 支持 / 推翻

## 论断

## 证据
""",
    "experience": """# {title}

- 日期：{date}
- 领域：benchmark / 数据归因 / 后训练 / 工程工具 / 论文写作
- 标签：
- 严重度：阻塞 / 返工 / 浪费时间

## 现象
贴报错原文，不要转述。

## 根因
不确定就写「推断，待确认」。

## 怎么发现的

## 以后怎么避免

## 证据
没有证据就写没有。
""",
}

SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class WikiError(Exception):
    pass


def resolve_root(arg):
    root = arg or os.environ.get("RESEARCH_WIKI_DIR")
    if not root:
        raise WikiError("没有指定数据目录：请用 --root 或设置环境变量 RESEARCH_WIKI_DIR")
    return pathlib.Path(root).expanduser()


def parse_id(node_id):
    if ":" not in node_id:
        raise WikiError(f"节点 id 要写成「类型:slug」，收到的是 {node_id!r}")
    t, slug = node_id.split(":", 1)
    if t not in TYPES:
        raise WikiError(f"未知类型 {t!r}，可选：{', '.join(TYPES)}")
    if not SLUG_RE.match(slug):
        raise WikiError(f"slug {slug!r} 只能用字母、数字、点、下划线、连字符")
    return t, slug


def page_path(root, node_id):
    t, slug = parse_id(node_id)
    return root / TYPES[t] / f"{slug}.md"


def require_init(root):
    if not (root / "graph" / "edges.jsonl").exists():
        raise WikiError(f"{root} 还没有初始化，先运行 init")


def all_nodes(root):
    nodes = {}
    for t, d in TYPES.items():
        for p in sorted((root / d).glob("*.md")):
            nodes[f"{t}:{p.stem}"] = p
    return nodes


def title_of(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem


def read_edges(root):
    edges = []
    f = root / "graph" / "edges.jsonl"
    for lineno, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                edges.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise WikiError(f"edges.jsonl 第 {lineno} 行不是合法 JSON：{e}")
    return edges


def log(root, text):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(root / "log.md", "a", encoding="utf-8") as f:
        f.write(f"- {now} {text}\n")


def cmd_init(root, _args):
    for d in list(TYPES.values()) + ["graph"]:
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "graph" / "edges.jsonl").touch()
    if not (root / "log.md").exists():
        (root / "log.md").write_text("# 变更记录（只追加）\n\n", encoding="utf-8")
    print(f"已初始化 {root}（已有内容不动）")


def cmd_new(root, args):
    require_init(root)
    node_id = f"{args.type}:{args.slug}"
    path = page_path(root, node_id)
    if path.exists():
        raise WikiError(f"{node_id} 已存在：{path}")
    date = datetime.date.today().isoformat()
    path.write_text(TEMPLATES[args.type].format(title=args.title, date=date), encoding="utf-8")
    log(root, f"new {node_id} — {args.title}")
    print(path)


def cmd_link(root, args):
    require_init(root)
    if args.rel not in RELATIONS:
        raise WikiError(f"未知关系 {args.rel!r}，可选：{', '.join(RELATIONS)}")
    for node_id in (args.src, args.dst):
        if not page_path(root, node_id).exists():
            raise WikiError(f"节点 {node_id} 不存在，先用 new 建页")
    if args.src == args.dst:
        raise WikiError("不能自己连自己")
    edges = read_edges(root)
    key = (args.src, args.rel, args.dst)
    if any((e["from"], e["rel"], e["to"]) == key for e in edges):
        print("这条关系已经存在，未重复写入")
        return
    edge = {"from": args.src, "rel": args.rel, "to": args.dst,
            "note": args.note or "", "date": datetime.date.today().isoformat()}
    with open(root / "graph" / "edges.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(edge, ensure_ascii=False) + "\n")
    log(root, f"link {args.src} --{args.rel}--> {args.dst}")
    print(f"{args.src} --{args.rel}--> {args.dst}")


def cmd_show(root, args):
    require_init(root)
    path = page_path(root, args.id)
    if not path.exists():
        raise WikiError(f"节点 {args.id} 不存在")
    print(path.read_text(encoding="utf-8").rstrip())
    edges = read_edges(root)
    out = [e for e in edges if e["from"] == args.id]
    inc = [e for e in edges if e["to"] == args.id]
    print("\n## 关系（由 graph/edges.jsonl 生成）")
    for e in out:
        print(f"- → {e['rel']} {e['to']}" + (f"（{e['note']}）" if e["note"] else ""))
    for e in inc:
        print(f"- ← {e['rel']} {e['from']}" + (f"（{e['note']}）" if e["note"] else ""))
    if not out and not inc:
        print("- （暂无）")


def cmd_search(root, args):
    require_init(root)
    nodes = all_nodes(root)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE VIRTUAL TABLE pages USING fts5(id UNINDEXED, title, body, tokenize='trigram')")
    for node_id, p in nodes.items():
        db.execute("INSERT INTO pages VALUES (?, ?, ?)", (node_id, title_of(p), p.read_text(encoding="utf-8")))
    terms = args.query.split()
    if not terms:
        raise WikiError("关键词不能为空")
    # trigram 分词至少要 3 个字符；短词（如中文双字词「飞书」）改用子串匹配，结果里会标出来
    long_terms = [t for t in terms if len(t) >= 3]
    short_terms = [t for t in terms if len(t) < 3]
    sql = "SELECT id, title, snippet(pages, 2, '[', ']', '…', 12) FROM pages"
    where, params = [], []
    if long_terms:
        where.append("pages MATCH ?")
        params.append(" AND ".join('"' + t.replace('"', '""') + '"' for t in long_terms))
    for t in short_terms:
        where.append("(title LIKE ? OR body LIKE ?)")
        params += [f"%{t}%", f"%{t}%"]
    sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY bm25(pages)" if long_terms else " ORDER BY id"
    sql += " LIMIT ?"
    params.append(args.k)
    rows = db.execute(sql, params).fetchall()
    if short_terms:
        print(f"（{'、'.join(short_terms)} 不足 3 个字符，用子串匹配）")
    if not rows:
        print("没有命中")
        return
    for node_id, title, snip in rows:
        snip = " ".join(snip.split())
        print(f"{node_id}  {title}\n    {snip}")


def cmd_lint(root, _args):
    require_init(root)
    nodes = all_nodes(root)
    problems = []
    seen = set()
    for e in read_edges(root):
        key = (e.get("from"), e.get("rel"), e.get("to"))
        if e.get("rel") not in RELATIONS:
            problems.append(f"未知关系：{key}")
        for end in (e.get("from"), e.get("to")):
            if end not in nodes:
                problems.append(f"关系指向不存在的节点 {end}：{key}")
        if key in seen:
            problems.append(f"重复关系：{key}")
        seen.add(key)
    for d in TYPES.values():
        for p in (root / d).glob("*.md"):
            if not SLUG_RE.match(p.stem):
                problems.append(f"文件名不合规（只能用字母、数字、点、下划线、连字符）：{p}")
    for msg in problems:
        print("❌ " + msg)
    print(f"共 {len(nodes)} 个节点；" + ("没有问题" if not problems else f"{len(problems)} 个问题"))
    return 1 if problems else 0


def cmd_index(root, _args):
    require_init(root)
    nodes = all_nodes(root)
    degree = {}
    for e in read_edges(root):
        for end in (e["from"], e["to"]):
            degree[end] = degree.get(end, 0) + 1
    lines = ["# 索引（由 wiki.py index 生成，不要手改）", ""]
    for t, d in TYPES.items():
        ids = [i for i in nodes if i.startswith(t + ":")]
        lines.append(f"## {d}（{len(ids)}）")
        lines += [f"- [{title_of(nodes[i])}]({d}/{nodes[i].name}) `{i}` · {degree.get(i, 0)} 条关系" for i in ids]
        lines.append("")
    (root / "index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"已写入 {root / 'index.md'}（{len(nodes)} 个节点）")


def main(argv=None):
    ap = argparse.ArgumentParser(description="轻量研究 wiki")
    ap.add_argument("--root", help="数据目录（默认读环境变量 RESEARCH_WIKI_DIR）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    p = sub.add_parser("new")
    p.add_argument("type", choices=list(TYPES))
    p.add_argument("slug")
    p.add_argument("title")
    p = sub.add_parser("link")
    p.add_argument("src")
    p.add_argument("rel")
    p.add_argument("dst")
    p.add_argument("--note")
    p = sub.add_parser("show")
    p.add_argument("id")
    p = sub.add_parser("search")
    p.add_argument("query")
    p.add_argument("-k", type=int, default=10)
    sub.add_parser("lint")
    sub.add_parser("index")
    args = ap.parse_args(argv)
    try:
        root = resolve_root(args.root)
        if args.cmd == "new" and not SLUG_RE.match(args.slug):
            raise WikiError(f"slug {args.slug!r} 只能用字母、数字、点、下划线、连字符")
        handler = globals()["cmd_" + args.cmd]
        return handler(root, args) or 0
    except WikiError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
