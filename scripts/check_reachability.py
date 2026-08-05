#!/usr/bin/env python3
"""ARK · 站点可达性检查（Reachability Check）

由巡航方法论沉淀而来（2026-07-31 / 08-01 连续两轮命中同型缺陷后固化）：

    「可达性检查」应与「可用性检查」并列。
    每新增一个页面，除验证 HTTP 200 外，必须验证全站至少存在 N 条入链，
    且其中至少 1 条位于漏斗上游（首页 / README）。
    200 只证明文件在，不证明用户走得到。

为什么需要它（三次真实命中）：
  1. 2026-07-31  proof-of-state-trap.html  上线 200，全站 **零入链**，实际曝光 0
  2. 2026-08-01  selfcheck.html            上线 200，仅 1 条入链且位于漏斗下游
  3. 2026-08-01  docs/reports/*.html       23 份诊断报告，**无索引页、首页零入链**

另一个必须自动化的理由：托管平台的 SPA fallback 会让**任意路径都返回 200**
（ARK 的 Cloudflare Pages 即如此——`/nonsense-xyz` 返回 200 + index.html 正文）。
因此「curl 拿到 200」根本不能证明页面存在，只有本地入链图才是可信信号。

用法：
    python scripts/check_reachability.py            # 检查，异常时非零退出
    python scripts/check_reachability.py --verbose  # 打印完整入链明细

判定模型：**传递可达性**（而非单级入链计数）。
从漏斗上游（首页 / README）出发做 BFS，能走到的页面即为可达。
这才符合真实站点结构：23 份诊断报告通过一个报告库索引页聚合，
叶子页只有 1 条入链（来自索引）是**正确架构**，不是缺陷。
若改用单级计数，会一口气报 21 条假告警——**一个吵的检查器等于没有检查器**。

退出码： 0 = 全部可达；1 = 存在不可达页面
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import deque
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"

# 漏斗上游：用户最可能的入口。非首页页面至少要有一条来自这里的入链。
UPSTREAM = {"docs/index.html", "README.md"}

# 首页、模板类、错误页不参与「被指向」检查
EXEMPT_TARGETS = {
    "docs/index.html",          # 首页自身即入口
    "docs/reports/template.html",  # 模板，非投放页
    "docs/reports/test-001.html",  # 测试夹具
    "docs/404.html",            # 错误页：无需入链（浏览器/CF 直接可达）
}

# 超过此距离的页面虽可达，但埋得太深，值得提醒
MAX_COMFORTABLE_DEPTH = 3


def source_files() -> list[Path]:
    files = [p for p in DOCS.rglob("*.html")]
    files += [p for p in DOCS.rglob("*.md")]
    readme = REPO / "README.md"
    if readme.exists():
        files.append(readme)
    return files


def target_pages() -> list[Path]:
    """需要被指向的投放页：docs 下的 html。"""
    return sorted(DOCS.rglob("*.html"))


def rel(p: Path) -> str:
    return str(p.relative_to(REPO))


def build_inlink_graph() -> dict[str, set[str]]:
    """返回 {目标页相对路径: {引用它的源文件相对路径}}。

    采用「文件名匹配」而非严格 URL 解析：页面同时被相对路径
    (`../reports/x.html`)、GitHub Pages 绝对路径和 pages.dev 无扩展名
    路由 (`/selfcheck`) 三种形式引用，文件名匹配对三者都稳健。
    """
    graph: dict[str, set[str]] = {rel(t): set() for t in target_pages()}

    for src in source_files():
        try:
            text = src.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        src_rel = rel(src)

        for target in target_pages():
            t_rel = rel(target)
            if t_rel == src_rel:
                continue  # 不计自引用
            stem = target.stem                      # e.g. "selfcheck"
            name = target.name                      # e.g. "selfcheck.html"
            # 带扩展名的引用，或 pages.dev 的无扩展名路由 /selfcheck
            hit = name in text or re.search(rf"/{re.escape(stem)}\b", text)
            # 目录形式的索引引用：/reports/ 指向 reports/index.html
            if not hit and target.name == "index.html":
                parent = target.parent.name
                if parent != "docs" and re.search(rf"/{re.escape(parent)}/", text):
                    hit = True
            if hit:
                graph[t_rel].add(src_rel)

    return graph


def compute_depths(graph: dict[str, set[str]]) -> dict[str, int]:
    """从漏斗上游 BFS，返回 {页面: 距上游的最短点击数}。不可达页不在结果中。"""
    # 反转入链图：{源: {它指向的目标}}
    out: dict[str, set[str]] = {}
    for target, srcs in graph.items():
        for s in srcs:
            out.setdefault(s, set()).add(target)

    depths: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque()
    for root in UPSTREAM:
        depths[root] = 0
        queue.append((root, 0))

    while queue:
        node, d = queue.popleft()
        for nxt in out.get(node, ()):
            if nxt not in depths or depths[nxt] > d + 1:
                depths[nxt] = d + 1
                queue.append((nxt, d + 1))
    return depths


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    graph = build_inlink_graph()
    depths = compute_depths(graph)

    pages = [p for p in sorted(graph) if p not in EXEMPT_TARGETS]
    orphans: list[str] = []
    unreachable: list[str] = []
    deep: list[tuple[str, int]] = []

    for page in pages:
        srcs = graph[page]
        d = depths.get(page)
        if args.verbose:
            depth_s = f"depth={d}" if d is not None else "UNREACHABLE"
            print(f"{page}  inlinks={len(srcs)}  {depth_s}")
            for s in sorted(srcs):
                print(f"     <- {s}")
        if not srcs:
            orphans.append(page)
        elif d is None:
            # 有入链，但入链源自身也走不到——整块子图从主干脱落
            unreachable.append(page)
        elif d > MAX_COMFORTABLE_DEPTH:
            deep.append((page, d))

    print("=" * 70)
    print("ARK 站点可达性检查（从首页/README 传递可达）")
    print(f"投放页总数: {len(pages)}")
    print("=" * 70)

    failed = False

    if orphans:
        failed = True
        print(f"\n🔴 孤岛页面（零入链）: {len(orphans)}")
        for p in orphans:
            print(f"   - {p}")

    if unreachable:
        failed = True
        print(f"\n🔴 不可达（有入链，但整块子图从首页走不到）: {len(unreachable)}")
        for p in unreachable:
            print(f"   - {p}  <- {', '.join(sorted(graph[p]))}")

    if deep:
        print(f"\n🟡 埋得较深（> {MAX_COMFORTABLE_DEPTH} 次点击）: {len(deep)}")
        for p, d in deep:
            print(f"   - {p}  (depth {d})")

    if not failed:
        by_depth: dict[int, int] = {}
        for p in pages:
            d = depths.get(p)
            if d is not None:
                by_depth[d] = by_depth.get(d, 0) + 1
        dist = "  ".join(f"depth{d}:{n}" for d, n in sorted(by_depth.items()))
        print(f"\n✅ 全部 {len(pages)} 个投放页均可从首页/README 走到。")
        print(f"   深度分布: {dist}")

    print()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
