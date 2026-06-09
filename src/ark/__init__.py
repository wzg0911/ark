"""
ARK - Agent Reliability Kit
Trust infrastructure for AI agents.

基因重组:
  🏦 Stripe → 幂等守护 (Idempotency Guard)
  ⚡ Sentinel → 熔断控制器 (Circuit Breaker)  
  👁 OpenTelemetry → 链路追踪 (Trace)
  🔧 IDE → 输出验证 (Output Validator)
  🎮 Gaming → 可靠性评分 (Reliability Score)
  📦 Community → Schema注册表 (Schema Registry)

v0.3.0 - Dashboard & Gamification
"""

from .guard import IdempotencyGuard
from .breaker import CircuitBreaker
from .validator import OutputValidator
from .trace import Trace
from .score import ReliabilityScore
from .schema_registry import SchemaRegistry
from .schema_hub import SchemaHub, get_schema_hub
from .auto import auto_init, detect_frameworks
from .dashboard import Dashboard, get_dashboard, Event
from .achievements import Achievements, Achievement, Tier
from .benchmarks import Benchmarks, BenchmarkResult

__version__ = "0.4.0.dev0"
__all__ = [
    "IdempotencyGuard", "CircuitBreaker", "OutputValidator", "Trace",
    "ReliabilityScore", "SchemaRegistry", "auto_init", "detect_frameworks",
    "Dashboard", "get_dashboard", "Event", "Achievements", "Achievement", "Tier",
    "Benchmarks", "BenchmarkResult",
    "SchemaHub", "get_schema_hub"
]
