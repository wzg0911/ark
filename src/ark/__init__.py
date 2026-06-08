"""
ARK - Agent Reliability Kit
Trust infrastructure for AI agents.

基因重组:
  🏦 Stripe → 幂等守护 (Idempotency Guard)
  ⚡ Sentinel → 熔断控制器 (Circuit Breaker)  
  👁 OpenTelemetry → 链路追踪 (Trace)
  🔧 IDE → 输出验证 (Output Validator)

v0.1.0 - MVP Core
"""

from .guard import IdempotencyGuard
from .breaker import CircuitBreaker
from .validator import OutputValidator
from .trace import Trace

__version__ = "0.1.0"
__all__ = ["IdempotencyGuard", "CircuitBreaker", "OutputValidator", "Trace"]
