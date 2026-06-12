"""
ARK OpenTelemetry 导出器 — 可靠性事件→OTLP标准格式
让ARK的幂等/熔断/验证事件流入Jaeger/Langfuse/Tempo/Zipkin

基因组合：
  🔭 OpenTelemetry — 业界标准OTLP协议
  🛡 ARK — 可靠性事件源
  🌊 Langfuse — LLM可观测性后端

设计原则：
  1. 零依赖：纯标准库实现 OTLP/JSON 格式（避免强制拉入 opentelemetry-api）
  2. 可选依赖：若安装了 opentelemetry-sdk，则用原生 SDK
  3. 三种事件类型：ark.idempotency.hit / ark.circuit.open / ark.validation.fail
  4. 一键开关：ARK_OTEL_ENDPOINT=http://collector:4318
"""

import os
import json
import time
import uuid
import logging
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """ARK 可靠性事件类型（OTel 语义约定扩展）"""
    IDEMPOTENCY_HIT = "ark.idempotency.hit"          # 命中重复调用
    IDEMPOTENCY_MISS = "ark.idempotency.miss"        # 首次调用
    CIRCUIT_OPEN = "ark.circuit.open"                # 熔断器打开
    CIRCUIT_CLOSE = "ark.circuit.close"              # 熔断器关闭
    CIRCUIT_HALF_OPEN = "ark.circuit.half_open"      # 半开探测
    VALIDATION_FAIL = "ark.validation.fail"          # 输出验证失败
    VALIDATION_PASS = "ark.validation.pass"          # 输出验证通过
    GUARDIAN_INTERCEPT = "ark.guardian.intercept"    # 预测性守护拦截


@dataclass
class ReliabilityEvent:
    """单条可靠性事件"""
    event_type: EventType
    timestamp_ns: int
    trace_id: str
    span_id: str
    tool_name: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    
    def to_otlp(self, service_name: str = "ark") -> Dict:
        """转换为 OTLP/JSON 格式（ResourceSpans 模型）"""
        severity = "ERROR" if self.error or self.event_type == EventType.VALIDATION_FAIL else "INFO"
        return {
            "resourceSpans": [{
                "resource": {
                    "attributes": [
                        {"key": "service.name", "value": {"stringValue": service_name}},
                        {"key": "service.version", "value": {"stringValue": "0.5.0"}},
                        {"key": "telemetry.sdk.name", "value": {"stringValue": "ark-trust"}},
                    ]
                },
                "scopeSpans": [{
                    "scope": {
                        "name": "ark.reliability",
                        "version": "0.5.0",
                    },
                    "spans": [{
                        "traceId": self.trace_id.zfill(32),
                        "spanId": self.span_id.zfill(16),
                        "name": self.event_type.value,
                        "kind": 1,  # INTERNAL
                        "startTimeUnixNano": str(self.timestamp_ns),
                        "endTimeUnixNano": str(self.timestamp_ns + int((self.duration_ms or 0) * 1_000_000)),
                        "status": {
                            "code": 2 if self.error else 1,  # ERROR or OK
                            "message": self.error or ""
                        },
                        "attributes": [
                            {"key": k, "value": _to_otlp_value(v)}
                            for k, v in self.attributes.items()
                        ]
                    }]
                }]
            }]
        }


def _to_otlp_value(v: Any) -> Dict:
    """将Python值转为OTLP AnyValue格式"""
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    if isinstance(v, (list, tuple)):
        return {"arrayValue": {"values": [_to_otlp_value(x) for x in v]}}
    return {"stringValue": str(v)}


class OTelExporter:
    """
    ARK OpenTelemetry 导出器
    
    用法:
        exporter = OTelExporter(endpoint="http://localhost:4318/v1/events")
        exporter.emit(ReliabilityEvent(...))
        
    或零配置（自动读取环境变量）:
        os.environ["ARK_OTEL_ENDPOINT"] = "http://collector:4318/v1/events"
        exporter = OTelExporter()
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        service_name: str = "ark",
        batch_size: int = 100,
        flush_interval: float = 5.0,
        enabled: bool = True,
    ):
        self.endpoint = endpoint or os.getenv("ARK_OTEL_ENDPOINT", "")
        self.service_name = service_name
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.enabled = enabled and bool(self.endpoint)
        
        self._buffer: List[ReliabilityEvent] = []
        self._lock = threading.Lock()
        self._total_emitted = 0
        self._total_dropped = 0
        self._last_flush = time.time()
        
        if not self.enabled:
            if not self.endpoint:
                logger.debug("ARK OTelExporter disabled: set ARK_OTEL_ENDPOINT to enable")
            else:
                logger.debug("ARK OTelExporter explicitly disabled")
    
    def emit(
        self,
        event_type: EventType,
        tool_name: str,
        trace_id: Optional[str] = None,
        span_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None,
    ) -> Optional[ReliabilityEvent]:
        """发送一条可靠性事件"""
        if not self.enabled:
            self._total_dropped += 1
            return None
        
        event = ReliabilityEvent(
            event_type=event_type,
            timestamp_ns=time.time_ns(),
            trace_id=trace_id or uuid.uuid4().hex,
            span_id=span_id or uuid.uuid4().hex[:16],
            tool_name=tool_name,
            attributes=attributes or {},
            duration_ms=duration_ms,
            error=error,
        )
        
        with self._lock:
            self._buffer.append(event)
            should_flush = (
                len(self._buffer) >= self.batch_size
                or (time.time() - self._last_flush) >= self.flush_interval
            )
        
        if should_flush:
            self.flush()
        
        self._total_emitted += 1
        return event
    
    def flush(self) -> int:
        """刷新缓冲区到OTel Collector"""
        if not self.enabled:
            return 0
        
        with self._lock:
            if not self._buffer:
                self._last_flush = time.time()
                return 0
            events = self._buffer[:]
            self._buffer.clear()
            self._last_flush = time.time()
        
        # 尝试用 httpx（ARK已有依赖）
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not installed; ARK OTel export skipped")
            self._total_dropped += len(events)
            return 0
        
        success = 0
        for event in events:
            payload = event.to_otlp(self.service_name)
            try:
                resp = httpx.post(
                    self.endpoint,
                    json=payload,
                    timeout=2.0,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code < 400:
                    success += 1
                else:
                    self._total_dropped += 1
            except Exception as e:
                logger.debug(f"ARK OTel export failed: {e}")
                self._total_dropped += 1
        
        return success
    
    def stats(self) -> Dict:
        """导出器统计"""
        return {
            "enabled": self.enabled,
            "endpoint": self.endpoint or "(not configured)",
            "buffered": len(self._buffer),
            "total_emitted": self._total_emitted,
            "total_dropped": self._total_dropped,
            "service_name": self.service_name,
        }
    
    def __repr__(self) -> str:
        return f"OTelExporter(enabled={self.enabled}, endpoint='{self.endpoint}', emitted={self._total_emitted})"


# 全局单例
_global_exporter: Optional[OTelExporter] = None
_global_lock = threading.Lock()


def get_otel_exporter(**kwargs) -> OTelExporter:
    """获取全局OTel导出器（单例）"""
    global _global_exporter
    with _global_lock:
        if _global_exporter is None:
            _global_exporter = OTelExporter(**kwargs)
        return _global_exporter


def reset_otel_exporter() -> None:
    """重置全局导出器（用于测试）"""
    global _global_exporter
    with _global_lock:
        _global_exporter = None
