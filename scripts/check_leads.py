#!/usr/bin/env python3
"""每日检查 guanyi2026@agent.qq.com 的 LEAD 邮件，写本地 CSV"""

import json, os, re
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

LEAD_FILE = Path.home() / ".hermes" / "projects" / "ark" / "data" / "leads.csv"
LOG_FILE = Path.home() / ".hermes" / "projects" / "ark" / "data" / "leads.json"

# 用 agently-cli 检查信件（v1.0.6+ 新语法：message +list，返回 JSON）
def fetch_and_check():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 已见线索的 inbox id 集合，用于去重（跨轮次幂等）
    seen = set()
    if LOG_FILE.exists():
        try:
            existing = json.loads(LOG_FILE.read_text())
            seen = {l.get("message_id", "") for l in existing if l.get("message_id")}
        except Exception:
            seen = set()

    import subprocess
    r = subprocess.run(
        ["agently-cli", "message", "+list", "--limit", "20", "--dir", "inbox"],
        capture_output=True, text=True, timeout=30
    )

    if r.returncode != 0:
        print(f"agently error: {r.stderr[:200]}")
        return

    try:
        payload = json.loads(r.stdout)
        messages = payload.get("data", {}).get("data", [])
    except Exception:
        print(f"agently parse error: {r.stdout[:200]}")
        return

    new_leads = []
    for msg in messages:
        # 字段兼容：新版 CLI 的字段名可能为 id/message_id、subject、snippet/body
        mid = str(msg.get("id") or msg.get("message_id") or "")
        subject = str(msg.get("subject") or "")
        snippet = str(msg.get("snippet") or msg.get("body") or "")
        text = subject + "\n" + snippet
        if "LEAD:" in text.upper():
            m = re.search(r'LEAD:\s*([^\s]+)', text, re.IGNORECASE)
            if m and mid and mid not in seen:
                email = m.group(1).strip()
                new_leads.append({
                    "email": email,
                    "source": "diagnose",
                    "captured_at": datetime.utcnow().isoformat() + "Z",
                    "message_id": mid
                })
                seen.add(mid)

    if new_leads:
        # 追加到 CSV
        with open(LEAD_FILE, "a") as f:
            if not LEAD_FILE.exists() or LEAD_FILE.stat().st_size == 0:
                f.write("email,source,captured_at,message_id\n")
            for l in new_leads:
                f.write(f"{l['email']},{l['source']},{l['captured_at']},{l['message_id']}\n")

        # 追加到 JSON 日志
        existing = []
        if LOG_FILE.exists():
            with open(LOG_FILE) as f:
                existing = json.load(f)
        existing.extend(new_leads)
        with open(LOG_FILE, "w") as f:
            json.dump(existing, f, indent=2)

        print(f"🆕 新线索 {len(new_leads)} 个: {', '.join(l['email'] for l in new_leads)}")
    else:
        print("📭 今日无新线索")

if __name__ == "__main__":
    fetch_and_check()
