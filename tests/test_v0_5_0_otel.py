"""v0.5.0 - OpenTelemetry 导出器测试"""

import json
import time
from unittest.mock import patch, MagicMock

import pytest

from ark.otel_exporter import (
    OTelExporter,
    ReliabilityEvent,
    EventType,
    get_otel_exporter,
    reset_otel_exporter,
    _to_otlp_value,
)


class TestEventType:
    """事件类型枚举"""

    def test_event_types_unique(self):
        types = [t.value for t in EventType]
        assert len(types) == len(set(types)), "事件类型必须唯一"

    def test_key_event_types_present(self):
        assert EventType.IDEMPOTENCY_HIT.value == "ark.idempotency.hit"
        assert EventType.CIRCUIT_OPEN.value == "ark.circuit.open"
        assert EventType.VALIDATION_FAIL.value == "ark.validation.fail"


class TestOTLPConversion:
    """OTLP 格式转换"""

    def test_basic_event_to_otlp(self):
        event = ReliabilityEvent(
            event_type=EventType.IDEMPOTENCY_HIT,
            timestamp_ns=1_000_000_000,
            trace_id="abc123",
            span_id="def456",
            tool_name="send_email",
            attributes={"key_id": "idem_001", "saved_ms": 250.5},
        )
        otlp = event.to_otlp(service_name="my-agent")
        
        assert "resourceSpans" in otlp
        rs = otlp["resourceSpans"][0]
        assert rs["resource"]["attributes"][0]["value"]["stringValue"] == "my-agent"
        
        span = rs["scopeSpans"][0]["spans"][0]
        assert span["name"] == "ark.idempotency.hit"
        assert span["traceId"] == "abc123".zfill(32)  # 32位
        assert span["spanId"] == "def456".zfill(16)   # 16位
        assert span["status"]["code"] == 1  # OK

    def test_error_event_status(self):
        event = ReliabilityEvent(
            event_type=EventType.VALIDATION_FAIL,
            timestamp_ns=time.time_ns(),
            trace_id="t1",
            span_id="s1",
            tool_name="llm_call",
            error="schema mismatch",
        )
        otlp = event.to_otlp()
        assert otlp["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["status"]["code"] == 2
        assert otlp["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["status"]["message"] == "schema mismatch"

    def test_value_type_conversion(self):
        assert _to_otlp_value(True) == {"boolValue": True}
        assert _to_otlp_value(42) == {"intValue": "42"}
        assert _to_otlp_value(3.14) == {"doubleValue": 3.14}
        assert _to_otlp_value("hi") == {"stringValue": "hi"}
        assert _to_otlp_value([1, 2])["arrayValue"]["values"][0] == {"intValue": "1"}


class TestOTelExporterDisabled:
    """未配置端点时应禁用"""

    def test_disabled_without_endpoint(self, monkeypatch):
        monkeypatch.delenv("ARK_OTEL_ENDPOINT", raising=False)
        exporter = OTelExporter()
        assert not exporter.enabled
        result = exporter.emit(EventType.IDEMPOTENCY_HIT, "tool")
        assert result is None
        stats = exporter.stats()
        assert stats["total_dropped"] == 1
        assert stats["total_emitted"] == 0

    def test_explicit_disable(self, monkeypatch):
        monkeypatch.setenv("ARK_OTEL_ENDPOINT", "http://localhost:4318")
        exporter = OTelExporter(enabled=False)
        assert not exporter.enabled
        exporter.emit(EventType.IDEMPOTENCY_HIT, "tool")
        assert exporter.stats()["total_dropped"] == 1


class TestOTelExporterBuffering:
    """批量缓冲行为"""

    def test_emit_increments_counter(self):
        exporter = OTelExporter(endpoint="http://localhost:4318/v1/events", batch_size=100)
        for i in range(5):
            exporter.emit(EventType.IDEMPOTENCY_HIT, f"tool_{i}")
        assert exporter.stats()["buffered"] == 5
        assert exporter.stats()["total_emitted"] == 5

    def test_auto_flush_on_batch_full(self):
        exporter = OTelExporter(endpoint="http://localhost:4318", batch_size=3)
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            for i in range(3):
                exporter.emit(EventType.IDEMPOTENCY_HIT, f"tool_{i}")
            assert mock_post.called
            mock_post.reset_mock()
            # 第二次填满也触发
            for i in range(3):
                exporter.emit(EventType.IDEMPOTENCY_HIT, f"tool_{i}")
            assert mock_post.called

    def test_flush_clears_buffer(self):
        exporter = OTelExporter(endpoint="http://localhost:4318")
        exporter.emit(EventType.IDEMPOTENCY_HIT, "tool")
        assert exporter.stats()["buffered"] == 1
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            exporter.flush()
        assert exporter.stats()["buffered"] == 0


class TestOTelExporterHTTP:
    """HTTP 发送行为"""

    def test_flush_posts_to_endpoint(self):
        exporter = OTelExporter(endpoint="http://collector:4318/v1/events")
        exporter.emit(
            EventType.CIRCUIT_OPEN,
            tool_name="flaky_api",
            attributes={"failure_count": 5},
        )
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            exporter.flush()
            assert mock_post.called
            args, kwargs = mock_post.call_args
            assert args[0] == "http://collector:4318/v1/events"
            assert "json" in kwargs
            # 验证 payload 是有效的 OTLP 结构
            payload = kwargs["json"]
            assert "resourceSpans" in payload
            assert payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["name"] == "ark.circuit.open"

    def test_flush_counts_failures(self):
        exporter = OTelExporter(endpoint="http://localhost:4318")
        exporter.emit(EventType.CIRCUIT_OPEN, "tool1")
        exporter.emit(EventType.CIRCUIT_OPEN, "tool2")
        
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=500)
            exporter.flush()
        assert exporter.stats()["total_dropped"] == 2

    def test_flush_handles_network_error(self):
        exporter = OTelExporter(endpoint="http://localhost:4318")
        exporter.emit(EventType.IDEMPOTENCY_HIT, "tool")
        with patch("httpx.post", side_effect=Exception("conn refused")):
            exporter.flush()
        assert exporter.stats()["total_dropped"] == 1


class TestGlobalSingleton:
    """全局单例"""

    def test_singleton_returns_same_instance(self, monkeypatch):
        monkeypatch.setenv("ARK_OTEL_ENDPOINT", "http://test:4318")
        reset_otel_exporter()
        a = get_otel_exporter()
        b = get_otel_exporter()
        assert a is b

    def test_reset_creates_new(self, monkeypatch):
        monkeypatch.setenv("ARK_OTEL_ENDPOINT", "http://test:4318")
        reset_otel_exporter()
        a = get_otel_exporter()
        reset_otel_exporter()
        b = get_otel_exporter()
        assert a is not b


class TestRealWorldScenarios:
    """真实场景：可靠性事件流"""

    def test_typical_agent_loop(self):
        """模拟Agent循环：3次幂等命中 + 1次熔断打开 + 1次验证失败"""
        exporter = OTelExporter(endpoint="http://otel:4318/v1/events")
        events = []
        
        # 5个工具调用
        for i in range(5):
            events.append(exporter.emit(
                EventType.IDEMPOTENCY_MISS,
                tool_name="search",
                trace_id="trace-1",
                span_id=f"span-{i}",
                duration_ms=120.0 + i * 10,
                attributes={"query": f"q{i}"},
            ))
        
        # 1个重复命中
        exporter.emit(
            EventType.IDEMPOTENCY_HIT,
            tool_name="search",
            trace_id="trace-1",
            span_id="span-dup",
            attributes={"saved_ms": 130.0},
        )
        
        # 1个熔断
        exporter.emit(
            EventType.CIRCUIT_OPEN,
            tool_name="flaky_api",
            trace_id="trace-1",
            attributes={"failure_count": 5, "threshold": 3},
        )
        
        # 1个验证失败
        exporter.emit(
            EventType.VALIDATION_FAIL,
            tool_name="llm_generate",
            trace_id="trace-1",
            error="output missing required field 'summary'",
        )
        
        assert exporter.stats()["buffered"] == 8
        assert all(e is not None for e in events)
