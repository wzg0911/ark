#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARK 增长指标采集器 (growth-tracker.py)
=====================================
采集 ARK 产品的可量化增长指标，维护时间序列，检测增长停滞 / 异常。

数据源（本机可采集）：
  - customers.json          本地邮件核销客户库（auto_redeem.py 写入）
  - redeem_log.jsonl        核销调度日志（每次运行 = 一次采集点）
  - redeem_processed.json   已处理邮件
  - diagnose.html           落地页（静态，仅审计 CTA 是否就位）
  - 线上站点                  HTTP 健康检查 + /api/verify 后端健康检查

输出：
  - 控制台结构化摘要
  - growth_report_<date>.md      当日快照报告
  - growth_metrics_history.jsonl 跨运行时间序列（趋势分析用）

退出码：
  0 = 正常；2 = 增长停滞 / 异常（供上游 cron / 告警消费）
"""
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent
CUSTOMERS = BASE / "customers.json"
REDEEM_LOG = BASE / "redeem_log.jsonl"
REDEEM_PROCESSED = BASE / "redeem_processed.json"
DIAGNOSE = BASE / "diagnose.html"
HISTORY = BASE / "growth_metrics_history.jsonl"
LIVE_SITE = "https://ark-6ek.pages.dev/diagnose"
VERIFY_EP = "https://ark-6ek.pages.dev/api/verify"
STATS_EP = "https://ark-6ek.pages.dev/api/stats"

# 真实漏斗落点：飞书 Bitable（前端经 /api/track 写入；/api/stats 依赖未绑定 KV，恒为 0）
# 密钥优先读环境变量（QClaw 飞书账号即 Ark 同款 app），缺失时回退工作区已知值。
FEISHU_APP_ID = (os.environ.get("ARK_FEISHU_APP_ID")
                 or os.environ.get("QCLAW_FEISHU_ACCOUNT_CLI_A949E8F4F2B85CC2_APPID") or "")
FEISHU_APP_SECRET = (os.environ.get("ARK_FEISHU_APP_SECRET")
                     or os.environ.get("QCLAW_FEISHU_ACCOUNT_CLI_A949E8F4F2B85CC2_APPSECRET") or "")
FEISHU_BITABLE = os.environ.get("ARK_FEISHU_BITABLE", "X3ZcbcJnHaCffBs2HVzcBR6Bnff")
FEISHU_TABLE = os.environ.get("ARK_FEISHU_TABLE", "tbleFRx9UgGHBqy9")

# 停滞判定阈值
STAG_HOURS = 3.0          # 启动后超过该时长且 0 客户 => 停滞
MIN_RUNS_FOR_TREND = 2    # 至少需要几次运行才有趋势意义


def now_utc():
    return datetime.now(timezone.utc)


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8") or "null") or default
        except Exception:
            return default
    return default


def http_get(url, timeout=12):
    try:
        req = urllib.request.Request(url, method="GET",
                                     headers={"User-Agent": "ARK-GrowthTracker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode("utf-8", "ignore")
        except Exception:
            return e.code, ""
    except Exception as e:
        return -1, str(e)  # -1 = 连接失败


def http_post_json(url, payload, timeout=12):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "ARK-GrowthTracker/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")[:200]
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, ""


def feishu_tenant_token():
    """取飞书 tenant_access_token（ARK 转化追踪同款 app）。"""
    if not (FEISHU_APP_ID and FEISHU_APP_SECRET):
        return None
    try:
        req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            d = json.loads(r.read())
        return d.get("tenant_access_token")
    except Exception:
        return None


def feishu_funnel():
    """聚合飞书 Bitable 中的真实转化漏斗（/api/track 落点）。"""
    token = feishu_tenant_token()
    if not token:
        return None
    try:
        agg = {"page_views": 0, "diagnosis_starts": 0, "claim_attempts": 0,
               "claim_success": 0, "pay_intents": 0, "customers": 0, "real_visitors": 0,
               "real_page_views": 0, "real_diagnosis_starts": 0, "real_claim_attempts": 0,
               "real_pay_intents": 0, "real_claim_success": 0, "real_customers": 0}
        url = (f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_BITABLE}/"
               f"tables/{FEISHU_TABLE}/records?page_size=100")
        seen = set()
        # 真实访客口径：匿名标识以 a_ 开头，且明显非测试标识
        # （排除 anon_test / a_test / a_check_* / a_preflight_* / a_track_* / a_*probe* / demo_* / cron-* 等）
        TEST_HINTS = ("anon_test", "_test", "test_", "a_test", "check", "preflight",
                      "track", "probe", "demo", "cron")
        def is_real_visitor(anon):
            if not anon or not anon.startswith("a_"):
                return False
            low = anon.lower()
            return not any(h in low for h in TEST_HINTS)
        while url:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=12) as r:
                d = json.loads(r.read())
            for rec in (d.get("records") or []):
                f = rec.get("fields", {}) or {}
                t = f.get("事件类型")
                anon = str(f.get("匿名标识", ""))
                is_real = is_real_visitor(anon)
                if t == "page_view":
                    agg["page_views"] += 1
                    if is_real and anon not in seen:
                        seen.add(anon); agg["real_visitors"] += 1
                        agg["real_page_views"] += 1
                elif t == "view":
                    agg["page_views"] += 1
                # 注意：前端真实事件名为 diagnosis_start（非 diagnose_start）
                elif t == "diagnosis_start":
                    agg["diagnosis_starts"] += 1
                    if is_real:
                        agg["real_diagnosis_starts"] += 1
                elif t in ("claim_attempt", "claim_pending"):
                    agg["claim_attempts"] += 1
                    if is_real:
                        agg["real_claim_attempts"] += 1
                elif t == "claim_success":
                    agg["claim_success"] += 1
                    if is_real:
                        agg["real_claim_success"] += 1
                elif t == "pay_intent":
                    agg["pay_intents"] += 1
                    if is_real:
                        agg["real_pay_intents"] += 1
                if f.get("邮箱(文本)"):
                    agg["customers"] += 1
                    if is_real:
                        agg["real_customers"] += 1
            if d.get("has_more") and d.get("page_token"):
                url = (f"https://open.feishu.cn/open-apis/bitable/v1/apps/{FEISHU_BITABLE}/"
                       f"tables/{FEISHU_TABLE}/records?page_size=100&"
                       f"page_token={urllib.parse.quote(d['page_token'])}")
            else:
                url = None
        return agg
    except Exception:
        return None


def parse_redeem_log():
    """解析核销日志，提取时间序列与累计指标。"""
    runs, scanned_total, redeem_events, last_total_customers = 0, 0, 0, 0
    first_ts, last_ts = None, None
    if REDEEM_LOG.exists():
        for line in REDEEM_LOG.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            ev = rec.get("event")
            ts = rec.get("ts")
            if ts:
                t = ts
                if first_ts is None or t < first_ts:
                    first_ts = t
                if last_ts is None or t > last_ts:
                    last_ts = t
            if ev == "run_start":
                runs += 1
            elif ev == "scanned":
                scanned_total += int(rec.get("count", 0) or 0)
            elif ev == "redeem":
                redeem_events += 1
            elif ev == "run_done":
                last_total_customers = int(rec.get("total_customers", 0) or 0)
                nr = int(rec.get("new_redeems", 0) or 0)
                redeem_events += nr
    return {
        "runs": runs,
        "scanned_total": scanned_total,
        "redeem_events": redeem_events,
        "last_total_customers": last_total_customers,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def parse_customers():
    cust = load_json(CUSTOMERS, {})
    if not isinstance(cust, dict):
        cust = {}
    created = [c.get("redeemed_at") for c in cust.values() if isinstance(c, dict)]
    created = [c for c in created if c]
    return {
        "total": len(cust),
        "by_source": _count_by(cust, "source"),
        "first_cust_ts": min(created) if created else None,
        "last_cust_ts": max(created) if created else None,
    }


def _count_by(cust, key):
    d = {}
    for c in cust.values():
        if isinstance(c, dict):
            d[c.get(key, "unknown")] = d.get(c.get(key, "unknown"), 0) + 1
    return d


def diagnose_cta_present():
    if not DIAGNOSE.exists():
        return False, "diagnose.html 缺失"
    txt = DIAGNOSE.read_text(encoding="utf-8")
    has_claim = "/api/claim" in txt or "openClaimModal" in txt
    has_verify = "/api/verify" in txt
    return has_claim and has_verify, f"claim={has_claim} verify={has_verify}"


def load_history():
    rows = []
    if HISTORY.exists():
        for line in HISTORY.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    return rows


def append_history(snapshot):
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def main():
    t0 = now_utc()
    cust = parse_customers()
    log = parse_redeem_log()
    processed = load_json(REDEEM_PROCESSED, {"message_ids": [], "emails": []})
    cta_ok, cta_note = diagnose_cta_present()

    # 线上健康检查
    site_status, _ = http_get(LIVE_SITE)
    site_up = site_status == 200
    verify_status, verify_body = http_post_json(VERIFY_EP,
                                                {"key": "ARK-TEST-TEST-49QF"})
    backend_ok = verify_status == 200

    # 真实漏斗数据源优先级（依据环境实测修正）：
    #  P1 = /api/stats（CF 端聚合飞书 Bitable，本环境最稳定；已正确聚合 diagnosis_start/diagnose_start/selfcheck_complete/selfcheck_cta，含 real_visitors）
    #  P2 = feishu_direct 仅作兜底（本机直连飞书偶发返回空 dict 而非 None，不可靠）
    #  注意：feishu_funnel() 失败时返回全 0 dict（非 None），必须显式判空，否则会“假成功”覆盖真实数据。
    #  2026-08-08 修复：前端新版事件名 = selfcheck_cta / selfcheck_complete / pay_modal_open / oss_cta（旧版 diagnosis_start 已弃用）。
    #  线上 /api/stats 已将新旧事件名统一聚合，此处只读 stats 即可，无需再等旧事件名。
    web_funnel = None
    funnel_source = None
    stats_status, stats_body = http_get(STATS_EP)
    if stats_status == 200 and stats_body:
        try:
            sd = json.loads(stats_body)
            if sd.get("ok"):
                web_funnel = {
                    "page_views": sd.get("page_views", 0),
                    "real_visitors": sd.get("real_visitors", 0),
                    "diagnosis_starts": sd.get("diagnosis_starts", 0),
                    "claim_attempts": sd.get("claim_attempts", 0),
                    "claim_success": sd.get("claim_success", 0),
                    "pay_intents": sd.get("pay_intents", 0),
                    "customers": sd.get("customers", 0),
                    "channels": sd.get("channels", {}),
                    "source": "api_stats",
                }
                funnel_source = "api_stats"
        except Exception:
            pass
    # 兜底：仅当 /api/stats 不可用时才用本机直连飞书（需显式判空）
    if web_funnel is None:
        _ff = feishu_funnel()
        _valid = _ff and any(_ff.get(k, 0) for k in ("page_views", "real_visitors", "diagnosis_starts", "claim_attempts", "pay_intents", "customers"))
        if _valid:
            _ff["source"] = "feishu_direct"
            web_funnel = _ff
            funnel_source = "feishu_direct"

    # 启动至今时长
    hours_since_launch = None
    if log["first_ts"]:
        try:
            ft = datetime.fromisoformat(log["first_ts"].replace("Z", "+00:00"))
            hours_since_launch = (t0 - ft).total_seconds() / 3600.0
        except Exception:
            hours_since_launch = None

    snapshot = {
        "ts": t0.isoformat(),
        "total_customers": cust["total"],
        "total_redeems": log["redeem_events"],
        "total_emails_scanned": log["scanned_total"],
        "redeem_runs": log["runs"],
        "emails_processed": len(processed.get("emails", []) or []),
        "site_up": site_up,
        "site_status": site_status,
        "backend_verify_status": verify_status,
        "backend_ok": backend_ok,
        "web_funnel": web_funnel,
        "funnel_source": "feishu_bitable" if web_funnel else "none",
        "cta_present": cta_ok,
        "hours_since_launch": round(hours_since_launch, 2) if hours_since_launch else None,
    }

    # 趋势（与上次快照对比）
    hist = load_history()
    prev = hist[-1] if hist else None
    delta_customers = (cust["total"] - prev["total_customers"]) if prev else cust["total"]
    delta_redeems = (log["redeem_events"] - prev["total_redeems"]) if prev else log["redeem_events"]

    # ===== 异常 / 停滞判定 =====
    alerts = []
    if cust["total"] == 0:
        alerts.append("NO_CUSTOMERS: 客户数为 0（产品已上线但无任何成交）")
    if hours_since_launch is not None and hours_since_launch >= STAG_HOURS and cust["total"] == 0:
        alerts.append(f"STAGNATION: 上线 {hours_since_launch:.1f}h 仍 0 客户（阈值 {STAG_HOURS}h）")
    if not site_up:
        alerts.append(f"SITE_DOWN: 落地页 HTTP {site_status}")
    if not backend_ok:
        alerts.append(f"BACKEND_BROKEN: /api/verify 返回 HTTP {verify_status}（核销/激活后端疑似未部署）")
    if not cta_ok:
        alerts.append(f"CTA_MISSING: 落地页转化入口缺失（{cta_note}）")
    # 盲点：仅当真实漏斗也读不到时才报
    if not web_funnel:
        alerts.append("BLIND_SPOT: 真实漏斗(飞书Bitable)不可读，仍以 /api/stats(未绑定KV)为盲区")
    else:
        # 真实漏斗可读：以「真实访客」口径判定泄漏，避免 demo/test 假人虚高转化掩盖真问题
        rv = web_funnel.get("real_visitors", 0)
        rd = web_funnel.get("real_diagnosis_starts", 0)
        rpi = web_funnel.get("real_pay_intents", 0)
        rca = web_funnel.get("real_claim_attempts", 0)
        if rv > 0 and rd == 0:
            alerts.append(f"FUNNEL_LEAK_T1: {rv} 真实访客有浏览但 0 进入诊断 → 落地页无法驱动真实用户进入诊断/CTA（顶层转化断流）")
        if rv > 0 and rpi == 0 and rca == 0:
            alerts.append(f"FUNNEL_LEAK_T2: {rv} 真实访客有浏览但 0 claim/支付意图 → 无一个真实用户走到转化（文案/CTA 未触发行动）")

    # 关键告警（硬故障）降权：真实漏斗可读时，NO_CUSTOMERS/STAGNATION 不再是“硬停”（流量真实存在）
    hard = any(a.startswith(("SITE_DOWN", "BACKEND_BROKEN")) for a in alerts)
    # 当真实漏斗可读且证明有流量时，NO_CUSTOMERS/STAGNATION 视为 WARN（转化问题而非获客问题）
    soft_cust = web_funnel and web_funnel.get("page_views", 0) > 0 and any(
        a.startswith(("NO_CUSTOMERS", "STAGNATION")) for a in alerts)
    if hard:
        alert_level = "CRITICAL"
    elif soft_cust or any(a.startswith(("FUNNEL_LEAK", "BLIND_SPOT")) for a in alerts) or alerts:
        alert_level = "WARN"
    else:
        alert_level = "OK"

    append_history(snapshot)

    # ===== 输出 =====
    lines = []
    lines.append("=" * 60)
    lines.append(f"📊 ARK 增长指标快照  {t0.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("=" * 60)
    lines.append(f"【核心指标】")
    lines.append(f"  累计客户数         : {cust['total']}  (本次增量 +{delta_customers})")
    lines.append(f"  累计核销/领取事件  : {log['redeem_events']}  (本次增量 +{delta_redeems})")
    lines.append(f"  邮件核销扫描累计    : {log['scanned_total']} 次 / 运行 {log['runs']} 次")
    lines.append(f"  已处理邮件          : {len(processed.get('emails', []) or [])}")
    lines.append(f"  客户来源分布        : {cust['by_source'] or '—'}")
    lines.append("")
    lines.append(f"【线上健康】")
    lines.append(f"  落地页              : HTTP {site_status}  ({'在线' if site_up else '异常'})")
    lines.append(f"  核销/验证后端       : HTTP {verify_status}  ({'正常' if backend_ok else '异常/未部署'})")
    lines.append(f"  落地页转化入口      : {'就位' if cta_ok else '缺失'} ({cta_note})")
    if web_funnel:
        pv = web_funnel.get('page_views', 0)
        dia = web_funnel.get('diagnosis_starts', 0)
        rv = web_funnel.get('real_visitors', 0)
        rpv = web_funnel.get('real_page_views', 0)
        rdia = web_funnel.get('real_diagnosis_starts', 0)
        rpi = web_funnel.get('real_pay_intents', 0)
        rca = web_funnel.get('real_claim_attempts', 0)
        conv = (dia / pv * 100) if pv else 0
        pay_conv = (web_funnel.get('pay_intents', 0) / pv * 100) if pv else 0
        rconv = (rdia / rv * 100) if rv else 0
        rpay_conv = (rpi / rv * 100) if rv else 0
        lines.append(f"  线上漏斗(飞书Bitable): 浏览 {pv} / 真实访客 {rv} / 诊断开始(全量) {dia} / claim尝试 {web_funnel.get('claim_attempts',0)} / 支付意图(全量) {web_funnel.get('pay_intents',0)} / 客户 {web_funnel.get('customers',0)}")
        lines.append(f"  全量转化           : 浏览→诊断 {conv:.1f}% | 浏览→支付意图 {pay_conv:.1f}%")
        lines.append(f"  ★真实访客漏斗     : 真实浏览 {rpv} / 真实诊断 {rdia} / 真实支付意图 {rpi} / 真实claim {rca}")
        lines.append(f"  ★真实转化(去假人)  : 真实访客→诊断 {rconv:.1f}% | 真实访客→支付意图 {rpay_conv:.1f}%")
    else:
        lines.append(f"  线上漏斗(飞书Bitable): 不可用（飞书密钥缺失 / 令牌获取失败）→ 仍以 /api/stats 为盲区")
    if hours_since_launch is not None:
        lines.append(f"  自上线(首次核销运行): {hours_since_launch:.1f} 小时")
    lines.append("")
    lines.append(f"【趋势】")
    if prev:
        lines.append(f"  上次采集 {prev['ts'][:19]} -> 本次 {t0.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"  客户数 {prev['total_customers']} -> {cust['total']}  | 核销 {prev['total_redeems']} -> {log['redeem_events']}")
    else:
        lines.append("  首次采集，暂无趋势基线")
    lines.append("")
    lines.append(f"【告警等级】 {alert_level}")
    for a in alerts:
        lines.append(f"  ⚠️  {a}")
    lines.append("=" * 60)

    out = "\n".join(lines)
    print(out)

    # 报告文件
    report = BASE / f"growth_report_{t0.strftime('%Y%m%d')}.md"
    report.write_text(out + "\n", encoding="utf-8")

    # 返回码：异常/停滞 = 2
    if alert_level == "CRITICAL":
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
