#!/usr/bin/env python3
"""ARK · 线上存在性检查（Live Existence Check）

由巡航方法论沉淀而来（2026-08-02 命中后固化）：

    Cloudflare Pages 的 SPA fallback 会让**任意不存在的路径也返回 HTTP 200**
    （正文为 index.html），因此「curl 拿到 200」根本不证明线上页面存在。

    本轮实测：`/nonsense-xyz-cruise` → HTTP 200 + index.html 正文（假绿实锤）。

判定模型：**内容指纹 + 语义差异 + 状态码**（2026-08-06 升级）。

    历史：Cloudflare Pages SPA fallback 曾让任意不存在路径返回 200+index.html（假绿），
    本脚本因此引入内容指纹判定。2026-08-06 新增 docs/404.html 根治：不存在路径现返回
    真实 404 + 专属 404 页。

    当前判定：
    1. 状态码 404 → 明确不存在（SPA 假绿已根治，状态码重新可信）。
    2. 状态码非 404 时，若正文与首页正文相同（fallback 特征）→ 判定「回退/疑似不存在」。
    3. 其余情况校验期望语义锚点（页面 title 关键词）。
       —— 锚点匹配到才算真正「存在」。

用法：
    python scripts/check_live_existence.py                 # 常规检查，异常非零退出
    python scripts/check_live_existence.py --verbose       # 打印每个页面的判定依据
    python scripts/check_live_existence.py --base https://ark-6ek.pages.dev

退出码：0 = 全部存在；1 = 存在疑似回退/不存在的页面；2 = 网络错误
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DEFAULT_BASE = "https://ark-6ek.pages.dev"

# 投放页：路径 → 期望出现在 <title>（或正文头部）的语义锚点
# 锚点必须选该页独有的关键词（以实际 <title> 为准），避免与 index.html 混淆
PAGES: dict[str, str] = {
    "/selfcheck": "自检清单",
    "/diagnose": "灌顶",
    "/proof-of-state-trap": "Proof",
    "/reports/": "报告库",
    "/api/stats": "{",
}

TIMEOUT = 20

# 负向路径：这些路径必须返回 404（SPA fallback 根治后的存在性反面证明）
# 任何一条返回 200 都说明 SPA fallback 假绿复发
NEGATIVE_PATHS = [
    "/nonsense-xyz-cruise",
    "/reports/does-not-exist",
    "/this-page-really-does-not-exist-12345",
]


def fetch(url: str) -> tuple[int, str]:
    """返回 (status, body)。HTTP 错误状态码也返回（urllib 对 404 会抛 HTTPError，需捕获）。"""
    req = urllib.request.Request(url, headers={"User-Agent": "ark-cruise/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        # 404 等错误状态码：读取错误正文（若有），返回真实状态码
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            body = ""
        return e.code, body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    base = args.base.rstrip("/")

    # 先取首页正文作为 SPA fallback 指纹，并单独校验首页存在性
    try:
        home_status, home_body = fetch(base + "/")
    except Exception as e:  # noqa: BLE001
        print(f"🔴 网络错误：无法访问 {base}/ ({e})")
        return 2
    if "ARK" not in home_body:
        print(f"🔴 首页正文缺少 ARK 语义锚点（body_len={len(home_body.strip())}）")
        return 1
    print(f"✅ {base}/  HTTP {home_status}  首页存在（语义锚点 'ARK' 命中）")

    home_norm = home_body.strip()
    print("=" * 70)
    print(f"ARK 线上存在性检查（内容指纹，base={base}）")
    print("=" * 70)
    print(f"首页正文指纹长度: {len(home_norm)} 字符")

    # 负向检查：不存在路径必须返回 404（SPA fallback 假绿复发检测）
    print("-" * 70)
    print("负向检查（不存在路径必须 404）")
    print("-" * 70)
    neg_failed = False
    for path in NEGATIVE_PATHS:
        url = base + path
        try:
            status, _ = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"🟡 {path:44s} 网络错误 {e}")
            neg_failed = True
            continue
        if status == 404:
            print(f"✅ {path:44s} HTTP 404（SPA 假绿未复发）")
        else:
            print(f"🔴 {path:44s} HTTP {status}  ← 应 404 却非 404，SPA fallback 假绿可能复发")
            neg_failed = True

    failed = neg_failed
    print()
    for path, anchor in PAGES.items():
        url = base + path
        try:
            status, body = fetch(url)
        except Exception as e:  # noqa: BLE001
            print(f"🔴 {path:24s} HTTP {status if 'status' in dir() else 'ERR'}  {e}")
            failed = True
            continue

        body_norm = body.strip()
        is_fallback = body_norm == home_norm
        anchor_hit = anchor.lower() in body_norm.lower()

        if args.verbose:
            print(f"  [{path}] status={status} body_len={len(body_norm)} "
                  f"fallback={is_fallback} anchor('{anchor}')={anchor_hit}")

        if is_fallback:
            print(f"🔴 {path:24s} HTTP {status}  ← SPA 回退（正文=首页指纹），页面疑似不存在")
            failed = True
        elif anchor_hit:
            print(f"✅ {path:24s} HTTP {status}  语义锚点 '{anchor}' 命中")
        else:
            print(f"🟡 {path:24s} HTTP {status}  正文与首页不同但锚点 '{anchor}' 未命中，需人工确认")
            failed = True

    print()
    if failed:
        print("结论：存在疑似回退/不存在的页面，或负向 404 检查失败，需处理（见 ROADMAP 假绿项）。")
        return 1
    print("结论：全部投放页线上存在 + 负向路径全部 404（SPA 假绿已根治，状态码重新可信）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
