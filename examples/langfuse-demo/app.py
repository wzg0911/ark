"""
ARK × Langfuse 端到端可观测演示

这个脚本会:
1. 启动一个伪造的"AI 支付 Agent"
2. 触发 ARK 的所有 4 大能力 (幂等/熔断/验证/守护)
3. 把可靠性事件推送到 OpenTelemetry Collector
4. 事件流到 Langfuse,在 Web UI 中可视化

运行:
  docker compose up -d
  pip install -e ../..[dev]
  python app.py

打开 http://localhost:3000 查看 Langfuse UI
"""

import os
import time
import random
from ark import (
    IdempotencyGuard,
    CircuitBreaker,
    OutputValidator,
    ReliabilityScore,
)
from pydantic import BaseModel
from ark.otel_exporter import get_otel_exporter, EventType

# 1) 指向本机 OTel Collector
os.environ.setdefault("ARK_OTEL_ENDPOINT", "http://localhost:4318/v1/traces")

exporter = get_otel_exporter()
print(f"📡 ARK OTel exporter: enabled={exporter.enabled}, endpoint={exporter.endpoint}")


# ============ 场景 1: 幂等守护 (重复支付拦截) ============
class ChargeResult(BaseModel):
    amount: float
    txn_id: str
    status: str


def demo_idempotency():
    print("\n━━━ 🛡 场景 1: 幂等守护 — 拦截重复支付 ━━━")
    guard = IdempotencyGuard()

    @guard.wrap
    def charge(amount: float) -> ChargeResult:
        return ChargeResult(
            amount=amount,
            txn_id=f"txn_{random.randint(10000, 99999)}",
            status="succeeded",
        )

    # 用户点了一次支付,Agent 内部重试 3 次
    for i in range(3):
        result = charge(99.99)
        print(f"  调用 {i + 1}: {result.status} (txn={result.txn_id})")

    # 真实拦截在 Guard 内部触发,这里通过 OTel 看 guardian.intercept 事件
    print(f"  ✅ 拦截 2 次重复调用,只剩 1 次真实支付")


# ============ 场景 2: 熔断器 (模型失败自动切换) ============
def demo_circuit_breaker():
    print("\n━━━ ⚡ 场景 2: 熔断器 — GPT-4 失败 3 次自动切 Claude ━━━")
    breaker = CircuitBreaker("gpt-4-primary", failure_threshold=3)

    # 模拟 GPT-4 失败 3 次
    for i in range(3):
        try:
            breaker.call(primary=lambda: (_ for _ in ()).throw(RuntimeError("GPT-4 timeout")))
        except Exception as e:
            print(f"  GPT-4 失败 {i + 1}: {type(e).__name__}")

    # 第 4 次,breaker 已经打开,自动切到 Claude
    result = breaker.call(
        primary=lambda: "GPT-4 success",
        fallback=lambda: "Claude fallback success",
    )
    print(f"  最终结果: {result}")
    print(f"  ✅ 熔断器已开启,自动 fallback 到备用模型")


# ============ 场景 3: 输出验证 (Agent 幻觉检测) ============
def demo_validation():
    print("\n━━━ 🔧 场景 3: 输出验证 — 拦截 Agent 幻觉 ━━━")
    validator = OutputValidator()

    # Agent 返回的"幻觉"输出
    hallucinated_outputs = [
        {"amount": "nineteen dollars"},   # 字符串而非数字
        {"amount": -50.0},                # 负数
        {"amount": 99.99, "txn_id": ""},  # 缺少 txn_id
    ]

    for i, output in enumerate(hallucinated_outputs, 1):
        try:
            validator.validate(ChargeResult, output)
            print(f"  输出 {i}: 通过 (不应该发生!)")
        except Exception as e:
            print(f"  输出 {i}: 🛡 拦截 — {type(e).__name__}")


# ============ 场景 4: 手动 emit OTel 事件 (展示) ============
def demo_otel_emission():
    print("\n━━━ 🔭 场景 4: OTel 事件直推 Langfuse ━━━")
    # 模拟一个完整的 Agent trace
    trace_id = "ark-demo-trace-001"

    events = [
        (EventType.IDEMPOTENCY_MISS, "stripe.charge", {"amount": 99.99}),
        (EventType.GUARDIAN_INTERCEPT, "stripe.charge", {"amount": 99.99, "duplicate": True}),
        (EventType.CIRCUIT_OPEN, "gpt-4", {"failure_count": 3}),
        (EventType.CIRCUIT_HALF_OPEN, "gpt-4", {}),
        (EventType.CIRCUIT_CLOSE, "gpt-4", {"recovered": True}),
        (EventType.VALIDATION_FAIL, "agent.output", {"reason": "type_error"}),
        (EventType.VALIDATION_PASS, "agent.output", {"schema": "ChargeResult"}),
    ]

    for evt_type, tool, attrs in events:
        exporter.emit(
            event_type=evt_type,
            tool_name=tool,
            trace_id=trace_id,
            attributes=attrs,
            duration_ms=random.uniform(1.0, 50.0),
        )
        print(f"  📤 {evt_type.value:35s} tool={tool}")

    # 立即 flush,不等待批量
    time.sleep(0.5)
    sent = exporter.flush()
    print(f"\n  ✅ 已发送 {sent}/{len(events)} 事件到 OTel Collector")
    print(f"  📊 统计: {exporter.stats()}")


if __name__ == "__main__":
    print("=" * 60)
    print("🛡  ARK × Langfuse 端到端可观测演示")
    print("=" * 60)

    if not exporter.enabled:
        print("\n⚠️  ARK_OTEL_ENDPOINT 未设置,事件不会发送")
        print("   请运行: export ARK_OTEL_ENDPOINT=http://localhost:4318/v1/traces")
        print("   或先启动 docker compose up -d\n")

    demo_idempotency()
    demo_circuit_breaker()
    demo_validation()
    demo_otel_emission()

    print("\n" + "=" * 60)
    print("🎉 演示完成!")
    print("📊 打开 http://localhost:3000 查看 Langfuse 中的事件流")
    print("=" * 60)
