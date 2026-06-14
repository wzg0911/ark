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
  🔮 memU → 预测性守护 (ProactiveGuard)
  💾 EverOS/MemBrain → 状态持久化 (StatefulBreaker)
  🧩 GenericAgent → 模块化能力 (ModuleKit)
  🤝 PraisonAI → 多Agent协议 (MultiAgentProtocol)

v0.5.0 - OpenTelemetry Exporter + Zero-Touch Instrumentation（生态接入点）
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
from .otel_exporter import OTelExporter, ReliabilityEvent, EventType, get_otel_exporter

__version__ = "0.5.3"
from .proactive import ProactiveGuard, ProactiveBlockError
from .stateful_breaker import StatefulBreaker, CircuitOpenError
from .module_kit import ModulePipeline, Module, RateLimitModule, SchemaValidationModule, LoggingModule, ModuleBlockError
from .multi_agent import MultiAgentProtocol, AgentMessage, AgentHeartbeat, MessageStatus, AgentStatus
from .errors import (
    truncate_error, error_to_llm_context, should_retry, retry_delay,
    ErrorContext, error_context, with_retry, NON_RETRYABLE_TYPES,
)
__all__ = [
    "IdempotencyGuard", "CircuitBreaker", "OutputValidator", "Trace",
    "ReliabilityScore", "SchemaRegistry", "auto_init", "detect_frameworks",
    "Dashboard", "get_dashboard", "Event", "Achievements", "Achievement", "Tier",
    "Benchmarks", "BenchmarkResult",
    "SchemaHub", "get_schema_hub",
    "ProactiveGuard", "ProactiveBlockError",
    "StatefulBreaker", "CircuitOpenError",
    "ModulePipeline", "Module", "RateLimitModule",
    "SchemaValidationModule", "LoggingModule", "ModuleBlockError",
    "MultiAgentProtocol", "AgentMessage", "AgentHeartbeat",
    "MessageStatus", "AgentStatus",
    # F9 Error Compressor
    "truncate_error", "error_to_llm_context", "should_retry", "retry_delay",
    "ErrorContext", "error_context", "with_retry", "NON_RETRYABLE_TYPES",
]
