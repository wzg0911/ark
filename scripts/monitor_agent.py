#!/usr/bin/env python3
"""监控官 — ARK 转化追踪埋点监控
职责：
1. 每 2 小时扫描 Bitable，检查是否有新埋点数据
2. 如果连续 6 小时无新数据 → 写入告警文件
3. 如果数据正常流动 → 每 6 小时（每 3 次）生成流量摘要
"""

import json, os, time, datetime

# === 配置 ===
STATE_FILE = os.path.expanduser("~/.openclaw/workspace/data/monitor_state.json")
SUMMARY_DIR = os.path.expanduser("~/.openclaw/workspace/复利飞轮系统/04-数据分析/")

# 飞书凭据（从 track.js 的环境看应该是硬编码在 CF 端，这里读取本地凭证）
FEISHU_APP_ID    = "cli_a949e8f4f2b85cc2"
FEISHU_APP_SECRET = "s9EHvwTkgXzlA2exwMhXFfLz3sijrE4j"
BITABLE_APP      = "X3ZcbcJnHaCffBs2HVzcBR6Bnff"
BITABLE_TABLE    = "tbleFRx9UgGHBqy9"

now = time.time()
os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
os.makedirs(SUMMARY_DIR, exist_ok=True)

# === 读取状态 ===
state = {"last_check_ts": 0, "last_new_data_ts": 0, "run_count": 0}
if os.path.exists(STATE_FILE):
    try:
        with open(STATE_FILE) as f:
            state = json.load(f)
    except:
        pass

state["run_count"] = state.get("run_count", 0) + 1
state["last_check_ts"] = now

# === 获取飞书 Token ===
import urllib.request
import urllib.error

def get_token():
    data = json.dumps({
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    resp = urllib.request.urlopen(req, timeout=10)
    result = json.loads(resp.read())
    return result.get("tenant_access_token", "")

def get_records(token, since_ts=None):
    """获取 Bitable 中的记录"""
    url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BITABLE_APP}/tables/{BITABLE_TABLE}/records?page_size=50"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read())
    if result.get("code") != 0:
        return None, f"Bitable API error: {result.get('msg','')}"
    records = result.get("data", {}).get("items", [])
    return records, None

# === 检查新数据 ===
token = get_token()
if not token:
    print("ERROR: 无法获取飞书 Token")
    exit(1)

records, err = get_records(token)
if err:
    print(f"ERROR: {err}")
    exit(1)

# 检查是否有最近 2 小时的新记录
# Bitable 创建记录没有时间戳字段，所以我们用"数量变化"来判断
# 上次检查时的记录数
last_count = state.get("last_record_count", 0)
current_count = len(records)
new_records = current_count - last_count
state["last_record_count"] = current_count

if new_records > 0:
    state["last_new_data_ts"] = now
    print(f"✅ 发现 {new_records} 条新记录（总计 {current_count}）")
else:
    print(f"ℹ️  无新记录（总计 {current_count}）")

# === 连续 6 小时无数据告警 ===
hours_since_new = (now - state["last_new_data_ts"]) / 3600
if hours_since_new >= 6 and state["last_new_data_ts"] > 0:
    print(f"⚠️  告警：已 {hours_since_new:.1f} 小时无新数据！")
    state["last_alert_ts"] = now
    # 写入告警标记文件（cron 的 announcement 会读取）
    alert_path = STATE_FILE.replace("monitor_state.json", "MONITOR_ALERT")
    with open(alert_path, "w") as f:
        f.write(f"ALERT: 埋点管道连续 {hours_since_new:.1f} 小时无新数据生成。\n")
        f.write(f"时间: {datetime.datetime.now().isoformat()}\n")
        f.write(f"Bitable 记录数: {current_count}\n")
elif state["last_new_data_ts"] == 0 and current_count == 0:
    print("⚠️  系统刚刚启动，尚无数据，不告警")

# === 每 3 次运行（约 6 小时）生成流量摘要 ===
run_count = state["run_count"]
if run_count % 3 == 0 and new_records >= 0:
    # 统计各类事件数量
    event_counts = {}
    channel_counts = {}
    for r in records:
        fields = r.get("fields", {})
        etype = fields.get("事件类型", "unknown")
        event_counts[etype] = event_counts.get(etype, 0) + 1
        ch = fields.get("来源渠道", "unknown")
        channel_counts[ch] = channel_counts.get(ch, 0) + 1

    summary = f"""# 监控官·流量摘要
生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
运行次数: #{run_count}
总埋点记录: {current_count}

## 事件分布
{json.dumps(event_counts, indent=2, ensure_ascii=False)}

## 来源渠道分布
{json.dumps(channel_counts, indent=2, ensure_ascii=False)}

## 运行状态
距上次新数据: {hours_since_new:.1f}h
"""
    summary_file = os.path.join(SUMMARY_DIR, f"流量摘要-{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.md")
    with open(summary_file, "w") as f:
        f.write(summary)
    print(f"📊 流量摘要已写入: {summary_file}")
    print(summary)

# === 保存状态 ===
with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)

print(f"✅ 监控官检查完成")
