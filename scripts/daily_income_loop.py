#!/usr/bin/env python3
"""每日收入循环：检查新线索 + 检查新支付 + 汇报状态"""

import json, subprocess, os, re
from datetime import datetime, timezone
from pathlib import Path

ARK_DIR = Path.home() / ".hermes" / "projects" / "ark"
LEAD_FILE = ARK_DIR / "data" / "leads.json"
REPORT_FILE = ARK_DIR / "data" / "daily_status.json"

def check_new_leads():
    """搜索刚到的 LEAD 邮件"""
    try:
        r = subprocess.run(
            ["agently-cli", "message", "+search", "--q", "LEAD:", "--limit", "10"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return [], f"agently error: {r.stderr[:200]}"
        
        d = json.loads(r.stdout)
        msgs = d.get("data", {}).get("data", [])
        return msgs, None
    except Exception as e:
        return [], str(e)

def check_new_payments():
    """搜索支付确认邮件"""
    try:
        r = subprocess.run(
            ["agently-cli", "message", "+search", "--q", "付款 已完成 key", "--limit", "10"],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return [], f"agently error: {r.stderr[:200]}"
        
        d = json.loads(r.stdout)
        msgs = d.get("data", {}).get("data", [])
        return msgs, None
    except Exception as e:
        return [], str(e)

def main():
    leads, lead_err = check_new_leads()
    payments, pay_err = check_new_payments()
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "new_leads": len(leads),
        "new_payments": len(payments),
        "lead_emails": [m.get("subject","?") for m in leads],
        "payment_subjects": [m.get("subject","?") for m in payments],
        "errors": [e for e in [lead_err, pay_err] if e]
    }
    
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w") as f:
        json.dump(report, f, indent=2)
    
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
