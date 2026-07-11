#!/usr/bin/env python3
"""每日检查 guanyi2026@agent.qq.com 的 LEAD 邮件，写本地 CSV"""

import json, os, re
from datetime import datetime
from pathlib import Path
from email.utils import parsedate_to_datetime

LEAD_FILE = Path.home() / ".hermes" / "projects" / "ark" / "data" / "leads.csv"
LOG_FILE = Path.home() / ".hermes" / "projects" / "ark" / "data" / "leads.json"

# 用 agently-cli 检查信件
def fetch_and_check():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # 用 agently 列出最近邮件
    import subprocess
    r = subprocess.run(
        ["agently-cli", "list-mail", "-a", "guanyi2026@agent.qq.com", "-n", "20"],
        capture_output=True, text=True, timeout=30
    )
    
    if r.returncode != 0:
        print(f"agently error: {r.stderr[:200]}")
        return
    
    lines = r.stdout.strip().split("\n")
    new_leads = []
    
    for line in lines:
        if "LEAD:" in line.upper():
            # 解析：提取邮箱和时间
            # LEAD: user@email.com from diagnose
            m = re.search(r'LEAD:\s*([^\s]+)', line, re.IGNORECASE)
            if m:
                email = m.group(1).strip()
                new_leads.append({
                    "email": email,
                    "source": "diagnose",
                    "captured_at": datetime.utcnow().isoformat() + "Z"
                })
    
    if new_leads:
        # 追加到 CSV
        with open(LEAD_FILE, "a") as f:
            if LEAD_FILE.stat().st_size == 0:
                f.write("email,source,captured_at\n")
            for l in new_leads:
                f.write(f"{l['email']},{l['source']},{l['captured_at']}\n")
        
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
