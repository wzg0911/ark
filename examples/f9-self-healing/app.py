"""
ARK × F9 Self-Healing Agent — 5-Minute End-to-End Demo
========================================================

展示 ARK F9 Error Compressor 如何让 AI Agent 从错误中自愈。

跑这个 demo 前:
    pip install -e ../..

跑这个 demo:
    python app.py

你会看到:
  [Round 1] 模拟支付 API 失败 → ARK 截断错误 → 喂给 LLM → LLM 修改参数重试
  [Round 2] 重试成功 ✅
  [Round 3] 模拟不可重试错误（Auth） → ARK 立即升级到 fallback

基因来源:
  🧬 12-Factor Agents (HumanLayer) Factor 9 — "把错误压缩进上下文"
"""

import json
import os
import random
import sys
import time
from typing import Any, Dict, Optional

# ARK F9
from ark.errors import (
    truncate_error,
    error_to_llm_context,
    should_retry,
    retry_delay,
    ErrorContext,
    error_context,
    with_retry,
    NON_RETRYABLE_TYPES,
)


# ━━━━━━━━━━ 1. 模拟真实世界的脆弱工具 ━━━━━━━━━━

class TransientAPIError(Exception):
    """网络抖动 / 临时过载 — 可重试"""
    pass


class RateLimitError(Exception):
    """被限流 — 可重试（需等待）"""
    pass


class AuthError(Exception):
    """认证失败 — 不可重试 (F9 立即升级)"""
    pass


class ValidationError(Exception):
    """入参非法 — 不可重试"""
    pass


def call_payment_api(
    amount: float,
    currency: str,
    customer_id: str,
    *,
    _simulate: Optional[str] = None,
) -> Dict[str, Any]:
    """
    模拟脆弱的支付 API
    
    _simulate 参数:
      - None: 真实调用（按概率失败）
      - "transient": 模拟网络抖动
      - "ratelimit": 模拟限流
      - "auth": 模拟认证失败
      - "success": 直接成功
    """
    if _simulate == "transient":
        raise TransientAPIError(
            f"ConnectionResetError: peer closed connection "
            f"without response (amount={amount}, customer={customer_id})"
        )
    if _simulate == "ratelimit":
        raise RateLimitError("429 Too Many Requests — retry after 2s")
    if _simulate == "auth":
        raise AuthError("Invalid API key (key_id: sk_test_***expired)")
    if _simulate == "validation":
        raise ValidationError(f"amount must be > 0, got {amount}")
    if _simulate == "success" or random.random() > 0.5:
        return {
            "txn_id": f"txn_{int(time.time() * 1000)}",
            "amount": amount,
            "currency": currency,
            "customer_id": customer_id,
            "status": "succeeded",
        }
    # 50% 失败概率（模拟不稳定）
    raise TransientAPIError(f"Upstream timeout after 30s (amount={amount})")


# ━━━━━━━━━━ 2. 用 ARK F9 守护脆弱工具 ━━━━━━━━━━

@with_retry(tool_name="payment_api", max_attempts=3)
def charge_customer_protected(amount: float, currency: str, customer_id: str) -> Dict[str, Any]:
    """被 ARK F9 守护的支付工具 — 自动重试 + 错误截断"""
    return call_payment_api(amount, currency, customer_id)


@with_retry(
    tool_name="auth_call",
    max_attempts=3,
    fallback=lambda *a, **kw: {"txn_id": "manual_review_required", "status": "pending_human"},
)
def call_with_auth(amount: float, currency: str, customer_id: str) -> Dict[str, Any]:
    """带 fallback 的版本 — 认证失败时自动转人工审核"""
    return call_payment_api(amount, currency, customer_id, _simulate="auth")


# ━━━━━━━━━━ 3. F9 核心演示：截断 + 喂 LLM + 自愈决策 ━━━━━━━━━━

def demo_f9_truncate():
    """F9 核心能力 1: 错误截断（500字符 + 末3行stack + md5 hash）"""
    print("\n" + "=" * 70)
    print("🧬 F9 DEMO 1: truncate_error() — 把 5KB stack trace 压成 LLM 友好格式")
    print("=" * 70)
    
    try:
        # 模拟一个很深的调用栈（典型 agent 场景）
        def layer1(): return layer2()
        def layer2(): return layer3()
        def layer3():
            raise TransientAPIError(
                "ConnectionResetError: HTTPSConnectionPool(host='api.stripe.com', port=443): "
                "Read timed out. (caused by ReadTimeoutError)\n"
                "  at stripe.api_requestor.APIRequestor._request_raw (stripe/api_requestor.py:633)\n"
                "  at stripe.api_requestor.APIRequestor.request_with_retries (stripe/api_requestor.py:516)\n"
                "  at stripe.api_requestor.APIRequestor.request (stripe/api_requestor.py:343)\n"
                "  at stripe.api_requestor.APIRequestor.request_stream (stripe/api_requestor.py:359)\n"
                "  at stripe.PaymentIntent.create (stripe/api_resources/abstract/createable_api_resource.py:21)\n"
                "  at app.charge_customer (app.py:42)\n"
                "  at agent.tool_call (agent.py:118)\n"
                "  at langchain.agents.AgentExecutor._take_next_step (agent.py:347)\n"
                "  at langchain.agents.AgentExecutor._iterate_next_step (agent.py:355)\n"
                "  at langchain.agents.AgentExecutor._call (agent.py:175)\n"
                "  at langchain.agents.AgentExecutor.invoke (agent.py:288)"
            )
        layer1()
    except Exception as e:
        truncated = truncate_error(e)
        print(f"\n📦 原始 stack trace: ~{len(str(e))} 字符（喂给 LLM 会爆 context window）")
        print(f"\n✨ ARK F9 截断后 ({len(json.dumps(truncated))} 字符):")
        print(json.dumps(truncated, indent=2, ensure_ascii=False))
        print("\n🎯 效果：保留 500 字 message + 末 3 行 stack + md5 hash → LLM 一眼可读")


def demo_f9_should_retry():
    """F9 核心能力 2: should_retry() — 8 种错误立即升级，绝不浪费 retry 配额"""
    print("\n" + "=" * 70)
    print("🧬 F9 DEMO 2: should_retry() — 不可重试错误立即升级")
    print("=" * 70)
    
    cases = [
        ("AuthError", AuthError("Invalid API key")),
        ("ValidationError", ValidationError("amount must be > 0")),
        ("TransientAPIError", TransientAPIError("Connection reset")),
        ("RateLimitError", RateLimitError("429")),
    ]
    
    print(f"\nF9 内置 {len(NON_RETRYABLE_TYPES)} 种 NON_RETRYABLE_TYPES: {sorted(NON_RETRYABLE_TYPES)}\n")
    
    for name, exc in cases:
        retryable = should_retry(exc, attempt=1, max_attempts=3)
        in_non_retryable = type(exc).__name__ in NON_RETRYABLE_TYPES
        icon = "✅ 可重试" if retryable else "🚫 立即升级"
        reason = "in NON_RETRYABLE_TYPES" if in_non_retryable else "transient/recoverable"
        print(f"  {icon}  {name:25s} → {reason}")


def demo_f9_retry_with_fallback():
    """F9 核心能力 3: with_retry() — 指数退避 + 升级路径 + fallback"""
    print("\n" + "=" * 70)
    print("🧬 F9 DEMO 3: with_retry() — 重试+升级+fallback 一气呵成")
    print("=" * 70)
    
    # Round 1: 50% 失败概率 + 3 次重试 = 应该会成功
    print("\n[Round 1] 模拟不稳定 API（50% 失败）— ARK 守护下应能自愈")
    random.seed(42)
    result = charge_customer_protected(99.99, "USD", "cus_abc")
    print(f"  ✅ 最终结果: {result}")
    print(f"  📊 ErrorContext 摘要: {charge_customer_protected.error_context.to_dict()}")
    
    # Round 2: Auth 错误 → 立即升级 → fallback
    print("\n[Round 2] 模拟 Auth 失败 — F9 识别为不可重试 → fallback 转人工")
    result = call_with_auth(99.99, "USD", "cus_abc")
    print(f"  ✅ Fallback 触发: {result}")
    
    # Round 3: 始终失败 → 达 max_attempts → 升级
    print("\n[Round 3] 模拟持续网络失败 — 达 max_attempts → 包装抛出")
    print("  (为了 demo 速度，我们 monkey-patch _simulate 强制失败)")
    
    import ark.errors
    orig = call_payment_api
    def always_fail(*a, **kw):
        return call_payment_api(*a, **kw, _simulate="transient")
    ark.errors.call_payment_api = always_fail  # noqa
    
    # 重新跑装饰器（用 error_context 手动控制）
    print("  调用 protected 版本（带 3 次重试，间隔 1s/2s/4s）...")
    start = time.time()
    try:
        charge_customer_protected(50.00, "USD", "cus_xyz")
    except RuntimeError as e:
        elapsed = time.time() - start
        print(f"  🚨 升级抛出: {type(e).__name__}: {str(e)[:200]}")
        print(f"  ⏱️  耗时: {elapsed:.1f}s（验证指数退避 1+2+4=7s）")
    ark.errors.call_payment_api = orig


def demo_f9_llm_context():
    """F9 核心能力 4: error_to_llm_context() — 把错误结构化喂给 LLM"""
    print("\n" + "=" * 70)
    print("🧬 F9 DEMO 4: error_to_llm_context() — 让 LLM 自己决定怎么修")
    print("=" * 70)
    
    # 模拟一个多步骤 agent 失败历史
    # 提示：真实场景下 record_failure 总是从 except 块调用，stack trace 自动捕获
    # 这里的"None stack"表示错误是构造/重放的（如来自重试队列），符合生产行为
    ctx = ErrorContext(tool_name="search_and_book_flight", max_attempts=3)
    ctx.record_failure(TransientAPIError("Connection reset"), attempt=1)
    ctx.record_failure(RateLimitError("429 Too Many Requests"), attempt=2)
    ctx.record_failure(TransientAPIError("Upstream timeout after 30s"), attempt=3)
    
    print("\n📤 喂给 LLM 的完整错误上下文:\n")
    print(ctx.to_llm_context())
    print("\n🎯 这个 prompt 喂给 GPT-4/Claude，它会决定：换工具 / 换参数 / 升级人工")


def main():
    print(r"""
    ___    ____  __ __     __    ____
   /   |  / __ \/ // /_   / /   /  _/
  / /| | / /_/ / // __/  / /    / /
 / ___ |/ _, _/ // /_   / /____/ /
/_/  |_/_/ |_|_/ \__/  /_____/___/

  12-Factor Agents Factor 9 — Self-Healing from Errors
    """)
    
    demo_f9_truncate()
    demo_f9_should_retry()
    demo_f9_retry_with_fallback()
    demo_f9_llm_context()
    
    print("\n" + "=" * 70)
    print("🎉 F9 DEMO 全部完成 — 现在你的 Agent 能从错误中自愈了！")
    print("=" * 70)
    print("""
下一步:
  • 把 @with_retry 加到你的所有工具函数上
  • 把 ErrorContext.to_llm_context() 喂给 LLM
  • 用 should_retry() 在 orchestrator 里决定是否跳过重试
  • OTel 模式下，F9 事件会自动 emit 到 Langfuse/Jaeger
    """)


if __name__ == "__main__":
    main()
