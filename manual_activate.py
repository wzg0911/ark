#!/usr/bin/env python3
"""
ARK 手动发货脚本（冷启动用）
用法：
  python3 manual_activate.py <邮箱>
  python3 manual_activate.py check          # 列出所有待发货申请
  python3 manual_activate.py list-pending   # 同上

逻辑：
  1. 读取 customers.json（本地，与 claim.js 的 KV 平行）
  2. 若该邮箱 status=pending_payment，生成 Pro Key，标记 delivered
  3. 输出可直接复制发给用户的邮件/私信文案

注意：这是人工确认的兜底流程。主人必须先在微信/支付宝确认收到 ¥49 后，
才运行此脚本发货。防止白嫖。
"""
import json, sys, os, secrets
from datetime import datetime, timedelta, timezone

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "customers.json")

def gen_key():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    rand = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"ARK-{rand[:4]}-{rand[4:]}-49QF"

def load():
    if not os.path.exists(DATA):
        return {}
    try:
        with open(DATA) as f:
            return json.load(f)
    except:
        return {}

def save(db):
    with open(DATA, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def list_pending(db):
    pending = [(e, c) for e, c in db.items() if c.get("status") == "pending_payment"]
    if not pending:
        print("✅ 无待发货申请")
        return
    print(f"📋 待发货申请（{len(pending)} 个）：")
    for e, c in pending:
        print(f"  - {e}  申请于 {c.get('createdAt','?')}")

def activate(email):
    db = load()
    email = email.lower().strip()
    if email not in db:
        db[email] = {"email": email, "status": "pending_payment",
                     "createdAt": datetime.now(timezone.utc).isoformat()}
    c = db[email]
    if c.get("status") == "delivered" and c.get("proKey"):
        print(f"⚠️  {email} 已发货，Pro Key = {c['proKey']}")
        return
    key = gen_key()
    c.update({
        "proKey": key,
        "status": "delivered",
        "deliveredAt": datetime.now(timezone.utc).isoformat(),
        "expiresAt": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
        "plan": "quick-fix-49",
        "amount": 49
    })
    db[email] = c
    save(db)
    print(f"✅ 已为 {email} 生成 Pro Key：{key}")
    print("—" * 50)
    print(f"""📧 发送给用户的文案（复制即可）：

主题：🎉 你的 ARK Pro Key 已激活！

{email} 你好，

感谢支持 ARK ¥49 快速修复版！你的 Pro Key 如下：

  {key}

激活步骤：
1. 打开 https://ark-6ek.pages.dev/diagnose
2. 滚动到页面底部「已有 Pro Key」
3. 粘贴 Pro Key，点击「激活」

下载工具包：https://ark-6ek.pages.dev/ark-init-kit-v1.zip

30 天 Pro 权限已开通。如有问题回复本邮件，或加客服微信。
ARK Team · 让你的智能体永不崩溃
""")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python3 manual_activate.py <邮箱> | check")
        sys.exit(1)
    arg = sys.argv[1]
    if arg in ("check", "list-pending"):
        list_pending(load())
    else:
        activate(arg)
