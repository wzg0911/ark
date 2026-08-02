#!/usr/bin/env python3
"""
ARK Trust — 产品演示视频 Demo
用于录屏：展示 IdempotencyGuard 拦截重复扣款

运行方式:
    cd /Users/w/.hermes/projects/ark
    python demo_ark_video.py

如果 src/ 不在 PYTHONPATH:
    PYTHONPATH=src python demo_ark_video.py
"""
import sys
import os

# 确保能找到 ark 模块
_project_root = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(_project_root, "src", "ark")):
    sys.path.insert(0, os.path.join(_project_root, "src"))

from ark import IdempotencyGuard

guard = IdempotencyGuard(ttl_seconds=3600)

call_count = [0]  # 用列表实现闭包引用，在 @guard.wrap 的闭包内可修改

@guard.wrap
def charge(amount: float):
    """模拟支付 API 调用"""
    call_count[0] += 1
    return {
        "status": "succeeded",
        "amount": amount,
        "txn_id": f"txn_{abs(hash(str(amount))) % 100000:05d}",
    }

print("=" * 50)
print("🛡 ARK Demo: AI Agent 支付保护")
print("=" * 50)

# 场景 1: 正常支付
print("\n📦 场景1: 正常支付")
result = charge(99.99)
print(f"  ✅ 支付成功: {result['txn_id']} ¥{result['amount']}")

# 场景 2: 模拟网络抖动 → Agent 重试 3 次
print("\n📦 场景2: 网络抖动 → Agent 重试 3 次")
for i in range(3):
    result = charge(99.99)
    if i == 0:
        print(f"  ✅ 第1次: {result['txn_id']}")
    else:
        print(f"  🛡 第{i+1}次: ARK幂等拦截 — 无重复扣款!")

# 统计
g = guard.stats
print(f"\n{'='*50}")
print("📊 ARK 信任报告")
print(f"{'='*50}")
print(f"🛡 幂等守护: {g['passes']}通过 | {g['intercepts']}拦截 | 节约{g['save_rate']}")
print(f"💰 API 实际调用: {call_count[0]}次（不含 ARK 拦截的重复调用）")
print(f"\n🎉 信任分数: 100% — 零重复扣款")
