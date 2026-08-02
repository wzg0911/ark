"""v0.5.3 - 原生 OTel SDK 桥接测试

设计原则 #2 的兑现：
  - 未安装 opentelemetry-api → 零依赖 OTLP/JSON 路径，不变
  - 已安装 → 同时把事件以原生 Span 形式交给用户 OTel pipeline
  - 桥接与 OTLP/JSON 并行，非替换
"""

import pytest
from unittest.mock import patch, MagicMock

from ark.otel_exporter import (
    OTelExporter,
    EventType,
    _to_otlp_value,
    _coerce_attr,
    _HAS_OTEL_SDK,
)


class TestCoerceAttr:
    """OTel attribute 类型安全转换"""

    def test_bool_preserved(self):
        assert _coerce_attr(True) is True
        assert _coerce_attr(False) is False

    def test_int_preserved(self):
        assert _coerce_attr(42) == 42
        assert isinstance(_coerce_attr(42), int)

    def test_float_preserved(self):
        assert _coerce_attr(3.14) == 3.14
        assert isinstance(_coerce_attr(3.14), float)

    def test_str_preserved(self):
        assert _coerce_attr("hello") == "hello"

    def test_list_recursed(self):
        out = _coerce_attr([1, "two", 3.0, True])
        assert out == [1, "two", 3.0, True]

    def test_unsupported_falls_back_to_str(self):
        # 字典/None/自定义对象 → str 化
        assert isinstance(_coerce_attr({"k": "v"}), str)
        assert _coerce_attr(None) == "None"


class TestNativeSDKAvailability:
    """SDK 可用性探测"""

    def test_has_otel_sdk_is_bool(self):
        assert isinstance(_HAS_OTEL_SDK, bool)

    def test_bridge_inactive_when_sdk_missing(self):
        """模拟 opentelemetry 不可用时，桥接必须自动失效"""
        with patch("ark.otel_exporter._HAS_OTEL_SDK", False), \
             patch("ark.otel_exporter._otel_trace", None):
            exporter = OTelExporter(
                endpoint="http://collector:4318/v1/events",
                use_native_sdk=True,
            )
            assert exporter.use_native_sdk is False
            assert exporter._otel_tracer is None

    def test_bridge_inactive_when_user_opt_out(self):
        """用户显式 use_native_sdk=False 时，绝不启用桥接"""
        exporter = OTelExporter(
            endpoint="http://collector:4318/v1/events",
            use_native_sdk=False,
        )
        assert exporter.use_native_sdk is False
        assert exporter._otel_tracer is None


class TestNativeSDKBridge:
    """SDK 桥接：与 OTLP/JSON 并行"""

    def _make_bridge(self):
        """构造一个桥接激活的 exporter（mock tracer）"""
        mock_tracer = MagicMock()
        mock_span_cm = MagicMock()
        mock_span_cm.__enter__ = MagicMock(return_value=MagicMock())
        mock_span_cm.__exit__ = MagicMock(return_value=False)
        mock_tracer.start_as_current_span = MagicMock(return_value=mock_span_cm)

        with patch("ark.otel_exporter._HAS_OTEL_SDK", True), \
             patch("ark.otel_exporter._otel_trace") as mock_mod:
            mock_mod.get_tracer = MagicMock(return_value=mock_tracer)
            exporter = OTelExporter(
                endpoint="http://collector:4318/v1/events",
                use_native_sdk=True,
            )
            exporter._mock_tracer = mock_tracer
            return exporter, mock_tracer

    def test_native_span_emitted_with_attributes(self):
        exporter, mock_tracer = self._make_bridge()
        event = exporter.emit(
            event_type=EventType.CIRCUIT_OPEN,
            tool_name="gpt-4",
            attributes={"failure_count": 5, "service": "primary"},
        )

        # 原生 tracer 收到一次 start_as_current_span 调用
        mock_tracer.start_as_current_span.assert_called_once()
        call_args, call_kwargs = mock_tracer.start_as_current_span.call_args
        # 第一个位置参数是 span name
        assert call_args[0] == "ark.circuit.open"
        # 属性中应含 ark.tool_name / ark.event_type
        attrs = call_kwargs.get("attributes", {})
        assert attrs.get("ark.tool_name") == "gpt-4"
        assert attrs.get("ark.event_type") == "ark.circuit.open"
        # 业务属性被加 ark. 前缀
        assert attrs.get("ark.failure_count") == 5
        assert attrs.get("ark.service") == "primary"
        # 事件仍返回，且 _last_native_spans +1
        assert event is not None
        assert exporter._last_native_spans == 1

    def test_validation_fail_marks_span_error(self):
        exporter, mock_tracer = self._make_bridge()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(return_value=mock_span)

        with patch.dict("sys.modules", {"opentelemetry.trace": MagicMock()}):
            from ark import otel_exporter
            with patch.object(otel_exporter, "_HAS_OTEL_SDK", True):
                exporter.emit(
                    event_type=EventType.VALIDATION_FAIL,
                    tool_name="payment",
                    error="amount mismatch",
                )

        # span.set_status 应被调用
        mock_span.set_status.assert_called_once()

    def test_native_emit_failure_does_not_break_otlp_path(self):
        """原生 span 创建失败时，OTLP/JSON 路径必须继续工作"""
        exporter, mock_tracer = self._make_bridge()
        mock_tracer.start_as_current_span.side_effect = RuntimeError("tracer broken")

        # 不应抛异常
        event = exporter.emit(
            event_type=EventType.IDEMPOTENCY_MISS,
            tool_name="charge",
        )
        # OTLP/JSON 路径仍收到事件（buffer 应有 1 条）
        assert event is not None
        assert len(exporter._buffer) == 1

    def test_stats_includes_native_bridge_info(self):
        # _make_bridge 用的是 module-level patch，stats() 也需读到一致状态
        with patch("ark.otel_exporter._HAS_OTEL_SDK", True):
            exporter, _ = self._make_bridge()
        exporter.emit(event_type=EventType.CIRCUIT_OPEN, tool_name="x")
        with patch("ark.otel_exporter._HAS_OTEL_SDK", True):
            stats = exporter.stats()
        bridge = stats["native_sdk_bridge"]
        assert bridge["active"] is True
        assert bridge["available"] is True
        assert bridge["native_spans_emitted"] == 1

    def test_stats_native_bridge_inactive_when_disabled(self):
        exporter = OTelExporter(
            endpoint="http://collector:4318/v1/events",
            use_native_sdk=False,
        )
        exporter.emit(event_type=EventType.CIRCUIT_OPEN, tool_name="x")
        stats = exporter.stats()
        bridge = stats["native_sdk_bridge"]
        assert bridge["active"] is False
        assert bridge["native_spans_emitted"] == 0


class TestBackwardCompat:
    """v0.5.3 必须 100% 向后兼容 v0.5.0/v0.5.1 公共 API"""

    def test_exporter_signature_compat(self):
        # 旧调用方式（无 use_native_sdk）必须仍工作
        exporter = OTelExporter(
            endpoint="http://collector:4318/v1/events",
            service_name="legacy-agent",
            batch_size=50,
            flush_interval=2.0,
            enabled=True,
        )
        assert exporter.service_name == "legacy-agent"
        assert exporter.batch_size == 50

    def test_to_otlp_value_unchanged(self):
        assert _to_otlp_value(True) == {"boolValue": True}
        assert _to_otlp_value(42) == {"intValue": "42"}
        assert _to_otlp_value(1.5) == {"doubleValue": 1.5}
        assert _to_otlp_value("x") == {"stringValue": "x"}
