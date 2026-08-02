#!/usr/bin/env python3
"""ARK · 投放页埋点覆盖检查（Instrumentation Coverage Check）

由巡航方法论沉淀而来（2026-08-02 命中「可达但不可见」缺陷后固化）：

    「可达性检查」证明用户**走得到**；
    「埋点覆盖检查」证明我们**知道他走过**。
    两者缺一，都会让站点在无声中失明。

为什么需要它（本轮真实命中）：

    2026-08-01 巡航修复了 23 份报告的零入链问题，并建了 check_reachability.py，
    结论「31 页全部可达 ✅」。但当天没有人问下一个问题：
    **这 31 个页面里，有几个在上报数据？**

    答案是 1 个（diagnose.html）。
    index / selfcheck / proof-of-state-trap / reports/index 全部零埋点。
    更讽刺的是 docs/track.js 这个专门为此写的采集层，**零页面引用，是死代码**。

    后果：/api/stats 报 86 page_views，看起来漏斗健康；
    但那 86 次几乎只来自诊断页。我们刚刚建好的报告库——ARK 最厚的证据资产——
    有没有人看，**在数据上完全不可知**。修好了入链，却看不见效果。

这与 F3 族「失败伪装成成功」同形：**统计数字非零，所以没人怀疑它不完整**。
一个只覆盖 1/31 页面的埋点系统，比完全没有埋点更危险——
它会持续输出看似可信的数字，让人据此做错误的内容决策。

判定模型：
  ① 每个投放页必须存在 page_view 上报路径（引用 /track.js 或页内 /api/track 埋点）
  ② track.js 若存在，必须至少被 1 个页面引用（否则是死代码）
  ③ 上报必须带 page 维度（否则无法归因到具体页面）

用法：
    python scripts/check_instrumentation.py            # 检查，异常时非零退出
    python scripts/check_instrumentation.py --verbose  # 打印逐页明细

退出码： 0 = 全部覆盖；1 = 存在失明页面
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DOCS = REPO / "docs"
TRACK_JS = DOCS / "track.js"

# 不参与埋点检查的页面：模板、测试夹具、纯跳转页
EXEMPT = {
    "docs/reports/template.html",   # 模板，非投放页
    "docs/reports/test-001.html",   # 测试夹具
    "docs/pro.html",                # 纯 meta refresh 跳转页
}


def target_pages() -> list[Path]:
    return sorted(DOCS.rglob("*.html"))


def rel(p: Path) -> str:
    return str(p.relative_to(REPO))


def has_pageview(text: str) -> tuple[bool, str]:
    """返回 (是否有 page_view 上报, 方式)。"""
    if re.search(r'src=["\'][^"\']*track\.js', text):
        return True, "track.js"
    if "/api/track" in text and "page_view" in text:
        return True, "inline"
    return False, "-"


def has_page_dim(text: str) -> bool:
    """上报是否带 page 归因维度。"""
    return bool(re.search(r"\bpage\s*:", text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    pages = [p for p in target_pages() if rel(p) not in EXEMPT]
    blind: list[str] = []
    no_dim: list[str] = []
    rows: list[tuple[str, str]] = []

    track_js_text = TRACK_JS.read_text(encoding="utf-8", errors="ignore") if TRACK_JS.exists() else ""
    track_js_refs = 0

    for p in pages:
        text = p.read_text(encoding="utf-8", errors="ignore")
        ok, how = has_pageview(text)
        if how == "track.js":
            track_js_refs += 1
        if not ok:
            blind.append(rel(p))
        else:
            # 归因维度：inline 埋点看自身，track.js 埋点看 track.js
            src = text if how == "inline" else track_js_text
            if not has_page_dim(src):
                no_dim.append(rel(p))
        rows.append((rel(p), how))

    print("=" * 70)
    print("ARK 投放页埋点覆盖检查")
    print(f"投放页总数（除豁免）: {len(pages)}")
    print("=" * 70)

    if args.verbose:
        for r, how in rows:
            mark = "✅" if how != "-" else "🔴"
            print(f"  {mark} {how:9s}  {r}")
        print()

    failed = False

    if blind:
        failed = True
        print(f"\n🔴 {len(blind)} 个页面零埋点（用户走得到，我们看不见）：")
        for b in blind:
            print(f"     - {b}")

    # 死代码检查：track.js 存在却无人引用
    if TRACK_JS.exists() and track_js_refs == 0:
        failed = True
        print("\n🔴 docs/track.js 存在但零页面引用 —— 死代码，采集层实际未生效。")

    if no_dim:
        failed = True
        print(f"\n🟡 {len(no_dim)} 个页面上报缺少 page 归因维度（只知有人来，不知看什么）：")
        for n in no_dim:
            print(f"     - {n}")

    if not failed:
        print(f"\n✅ 全部 {len(pages)} 个投放页均有 page_view 上报且带 page 归因维度。")
        print(f"   track.js 被引用: {track_js_refs} 页")
        return 0

    print("\n提示：为页面 <head> 添加 `<script src=\"/track.js\" defer></script>` 即可自动上报。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
