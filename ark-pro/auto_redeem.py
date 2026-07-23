#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARK 信任模式自动核销 v2 (auto_redeem.py)
================================================
模式：信任模式（B1）+ 单档 ¥49 快速修复
适用：07-23 后临时使用主人个人微信/支付宝商家码
特点：
  - 用户扫码 ¥49 → 提交邮箱 → 立即发 Pro Key
  - 无需人工审核（首个 1-3 个客户纯信任，后续可加 WeChat 验证）
  - 30 天有效期

核销识别方式：
  1. 收件箱：扫描 "I want ARK Pro Key" 主题的邮件（来自用户提交）
  2. 备用：附件截图（用户主动发送付款凭证）

用法：
  python3 auto_redeem.py              # 正常核销
  python3 auto_redeem.py --dry-run    # 只识别不发送
  python3 auto_redeem.py --send-key <email>  # 手动发送 Key（兜底）
"""
import json
import subprocess
import sys
import re
import time
import hashlib
import os
import smtplib
import secrets
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

BASE = Path(__file__).resolve().parent
CUSTOMERS = BASE / "customers.json"
PROCESSED = BASE / "redeem_processed.json"
LOG = BASE / "redeem_log.jsonl"
WELCOME_TXT = BASE / "welcome_email_body.txt"
PAYMENTS_DIR = BASE / "payments"

AGENTLY = "agently-cli"
DRY_RUN = "--dry-run" in sys.argv
MANUAL_SEND = None
for i, arg in enumerate(sys.argv):
    if arg == "--send-key" and i + 1 < len(sys.argv):
        MANUAL_SEND = sys.argv[i + 1]
        break

# 产品配置
PRODUCT_CONFIG = {
    "quick-fix-49": {
        "name": "ARK 快速修复版",
        "amount": 49,
        "validity_days": 30,
        "features": ["一键修复全部问题", "下载完整配置包", "30天Pro权限", "7天无理由退款"]
    }
}

# QQ Mail SMTP（备用方案，agently-cli 失败时使用）
QQ_SMTP = {
    "host": "smtp.qq.com",
    "port": 465,
    "user": "guanyi2026@agent.qq.com",
    "pass": os.environ.get("QQ_MAIL_AUTH_CODE", ""),  # 从环境变量读取授权码
}

WELCOME_SUBJECT = "🎉 欢迎加入 ARK — 你的 Pro Key + 30 天权限已激活"


def log(event, **kw):
    rec = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **kw}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[{event}] " + " ".join(f"{k}={v}" for k, v in kw.items()))


def run_cli(args):
    """调用 agently-cli，返回解析后的 JSON（失败返回 None）"""
    try:
        r = subprocess.run([AGENTLY] + args, capture_output=True,
                           text=True, timeout=60)
        if r.returncode != 0:
            log("cli_error", args=" ".join(args), stderr=r.stderr[:200])
            return None
        out = r.stdout.strip()
        start = out.find("{")
        if start < 0:
            return None
        return json.loads(out[start:])
    except Exception as e:
        log("cli_exc", args=" ".join(args), err=str(e)[:200])
        return None


def load_json(path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8") or "null") or default
        except Exception:
            return default
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def gen_key(email):
    """生成 Pro Key：ARK-XXXX-XXXX-49QF（49=¥49, QF=QuickFix）"""
    rand = secrets.token_hex(4).upper()
    return f"ARK-{rand[:4]}-{rand[4:]}-49QF"


def welcome_body(user_email, pro_key):
    """读取欢迎邮件模板，填充 Pro Key 和邮箱"""
    if WELCOME_TXT.exists():
        body = WELCOME_TXT.read_text(encoding="utf-8")
    else:
        body = "你的 ARK Pro Key: {{pro_key}}"
    return body.replace("{{user_email}}", user_email).replace("{{pro_key}}", pro_key)


def send_via_agently(to_email, subject, body):
    """通过 agently-cli 发送邮件（主路径）"""
    res = run_cli(["message", "+send", "--to", to_email,
                   "--subject", subject, "--body", body])
    return bool(res and res.get("ok"))


def send_via_smtp(to_email, subject, body):
    """通过 QQ SMTP 发送（备用路径）"""
    if not QQ_SMTP["pass"]:
        log("smtp_no_auth_code")
        return False
    try:
        msg = MIMEMultipart()
        msg["From"] = QQ_SMTP["user"]
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        with smtplib.SMTP_SSL(QQ_SMTP["host"], QQ_SMTP["port"], timeout=30) as s:
            s.login(QQ_SMTP["user"], QQ_SMTP["pass"])
            s.send_message(msg)
        return True
    except Exception as e:
        log("smtp_exc", err=str(e)[:200])
        return False


def send_welcome(to_email, pro_key):
    """发送欢迎邮件（双路径兜底）"""
    if DRY_RUN:
        log("dry_send", to=to_email, key=pro_key)
        return True
    body = welcome_body(to_email, pro_key)
    if send_via_agently(to_email, WELCOME_SUBJECT, body):
        log("welcome_sent_agently", to=to_email, key=pro_key)
        return True
    if send_via_smtp(to_email, WELCOME_SUBJECT, body):
        log("welcome_sent_smtp", to=to_email, key=pro_key)
        return True
    log("welcome_fail", to=to_email)
    return False


def is_claim_mail(msg):
    """判断是否是"领取 Pro Key"的邮件（信任模式）"""
    subject = (msg.get("subject", "") + " " + msg.get("snippet", "")).lower()
    # 关键词：I want / 想要 / 申请 / 领取 / 升级 / pro key / ark
    claim_kws = ["i want ark pro key", "ark pro key", "申请ark",
                 "领取pro", "升级ark", "想要ark", "ark pro"]
    for kw in claim_kws:
        if kw in subject:
            return True, f"claim_keyword:{kw}"
    # 附件也算（用户主动发付款凭证）
    if msg.get("has_attachments"):
        return True, "has_attachment"
    return False, ""


def mark_read(message_id):
    if DRY_RUN:
        return
    run_cli(["message", "+read", "--id", message_id])


def manual_send_key(email):
    """手动模式：直接为指定邮箱生成 Pro Key 并发送"""
    if not email or "@" not in email:
        print("❌ 用法: python3 auto_redeem.py --send-key <email>")
        return False
    customers = load_json(CUSTOMERS, {})
    processed = load_json(PROCESSED, {"message_ids": [], "emails": []})
    email_l = email.strip().lower()
    if email_l in customers:
        existing = customers[email_l]
        print(f"⚠️ {email} 已有 Pro Key: {existing.get('key')}")
        print(f"   创建时间: {existing.get('redeemed_at')}")
        print(f"   来源: {existing.get('source', 'N/A')}")
        if input("重新发送? (y/n): ").lower() != "y":
            return False
        pro_key = existing["key"]
    else:
        pro_key = gen_key(email_l)
        customers[email_l] = {
            "key": pro_key,
            "redeemed_at": datetime.now(timezone.utc).isoformat(),
            "source": "manual_send_key",
            "product": "quick-fix-49",
            "validity_days": 30,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "amount_paid": 49,
        }
        save_json(CUSTOMERS, customers)
    if send_welcome(email_l, pro_key):
        print(f"✅ Pro Key 已发送: {pro_key}")
        return True
    print(f"❌ 发送失败，Key 已生成在 customers.json 中，请手动发送")
    return False


def main():
    if MANUAL_SEND:
        manual_send_key(MANUAL_SEND)
        return

    log("run_start", dry_run=DRY_RUN, mode="trust-v2")
    customers = load_json(CUSTOMERS, {})
    processed = load_json(PROCESSED, {"message_ids": [], "emails": []})

    res = run_cli(["message", "+list", "--limit", "30"])
    if not res or not res.get("ok"):
        log("list_fail")
        return
    msgs = res.get("data", {}).get("data", [])
    log("scanned", count=len(msgs))

    new_redeems = 0
    for msg in msgs:
        mid = msg.get("message_id")
        if not mid or mid in processed["message_ids"]:
            continue
        if msg.get("is_read"):
            processed["message_ids"].append(mid)
            continue
        is_claim, reason = is_claim_mail(msg)
        if not is_claim:
            continue
        frm = msg.get("from", {})
        user_email = frm.get("email", "").strip().lower()
        if not user_email or user_email in ("admin@agent.qq.com", "guanyi2026@agent.qq.com"):
            processed["message_ids"].append(mid)
            continue
        # 幂等：同邮箱已有 Key 跳过（但标记处理）
        if user_email in customers:
            log("dup_email_skip", email=user_email, mid=mid)
            processed["message_ids"].append(mid)
            mark_read(mid)
            continue

        # === 核销 ===
        pro_key = gen_key(user_email)
        customers[user_email] = {
            "key": pro_key,
            "redeemed_at": datetime.now(timezone.utc).isoformat(),
            "source_msg": mid,
            "detect_reason": reason,
            "product": "quick-fix-49",
            "validity_days": 30,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "amount_paid": 49,
        }
        log("redeem", email=user_email, key=pro_key, reason=reason)

        if send_welcome(user_email, pro_key):
            processed["emails"].append(user_email)
            processed["message_ids"].append(mid)
            mark_read(mid)
            new_redeems += 1
        else:
            log("redeem_pending_retry", email=user_email)

    if not DRY_RUN:
        save_json(CUSTOMERS, customers)
        save_json(PROCESSED, processed)
    log("run_done", new_redeems=new_redeems, total_customers=len(customers))


if __name__ == "__main__":
    main()
