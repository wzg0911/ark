"""
ARK v0.5.0 OTel 集成测试
验证核心组件（Guard / Breaker / Validator）在OTel开启时自动emit事件
零配置（OTel关闭）下行为完全不变
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ark.guard import IdempotencyGuard
from ark.breaker import CircuitBreaker
from ark.validator import OutputValidator, ValidationResult
from pydantic import BaseModel


# ===== Part 1: 零配置行为不变（OTel 关闭） =====

class TestOtelDisabled:
    """验证没配 ARK_OTEL_ENDPOINT 时，行为与 v0.4.0 完全一致"""
    
    def setup_method(self):
        # 强制清空 env
        os.environ.pop("ARK_OTEL_ENDPOINT", None)
        # 重置全局exporter
        try:
            from ark.otel_exporter import reset_otel_exporter
            reset_otel_exporter()
        except Exception:
            pass
    
    def test_guard_basic_idempotency(self):
        """幂等守护在OTel关闭时正常工作"""
        guard = IdempotencyGuard()
        
        @guard.wrap
        def charge(amount: float):
            return {"charged": amount}
        
        assert charge(99.99) == {"charged": 99.99}
        assert charge(99.99) == {"charged": 99.99}  # 拦截
        assert guard.intercepts == 1
        assert guard.passes == 1
    
    def test_breaker_basic_circuit(self):
        """熔断器在OTel关闭时正常工作"""
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        
        def fail():
            raise ValueError("boom")
        
        with pytest.raises(ValueError):
            cb.call(fail)
        with pytest.raises(ValueError):
            cb.call(fail)
        assert cb.state == "open"
    
    def test_validator_basic(self):
        """验证器在OTel关闭时正常工作"""
        v = OutputValidator()
        
        class S(BaseModel):
            x: int
            y: str
        
        result = v.validate(S, {"x": 1, "y": "ok"})
        assert result.valid
        
        result = v.validate(S, {"x": "wrong", "y": "ok"})
        assert not result.valid
        assert v.blocked == 1


# ===== Part 2: OTel 开启时的自动emit =====

class TestOtelEnabledIntegration:
    """验证核心组件开启OTel时自动emit事件"""
    
    def setup_method(self):
        os.environ["ARK_OTEL_ENDPOINT"] = "http://mock-collector:4318/v1/events"
        from ark.otel_exporter import reset_otel_exporter
        reset_otel_exporter()
        # 每个测试都mock掉 httpx.post 避免真实网络
        self._mock_post = patch("httpx.post")
        self._mock_post.start()
    
    def teardown_method(self):
        self._mock_post.stop()
        os.environ.pop("ARK_OTEL_ENDPOINT", None)
        from ark.otel_exporter import reset_otel_exporter
        reset_otel_exporter()
    
    def test_guard_emits_on_intercept(self):
        """幂等守护拦截时自动emit guardian.intercept"""
        guard = IdempotencyGuard()
        
        @guard.wrap
        def send_email(to: str, body: str):
            return f"sent to {to}"
        
        send_email("a@b.com", "hi")  # miss
        send_email("a@b.com", "hi")  # hit (intercepted)
        
        # 验证exporter收到了事件
        from ark.otel_exporter import get_otel_exporter, EventType
        exporter = get_otel_exporter()
        # 触发flush前先检查buffer
        assert len(exporter._buffer) >= 1
        
        types_in_buffer = [e.event_type for e in exporter._buffer]
        assert EventType.IDEMPOTENCY_MISS in types_in_buffer
        assert EventType.GUARDIAN_INTERCEPT in types_in_buffer
    
    def test_breaker_emits_on_open(self):
        """熔断器打开时自动emit circuit.open"""
        cb = CircuitBreaker("api", failure_threshold=2, recovery_timeout=60)
        
        def fail():
            raise RuntimeError("api down")
        
        with pytest.raises(RuntimeError):
            cb.call(fail)
        with pytest.raises(RuntimeError):
            cb.call(fail)
        
        from ark.otel_exporter import get_otel_exporter, EventType
        exporter = get_otel_exporter()
        types_in_buffer = [e.event_type for e in exporter._buffer]
        assert EventType.CIRCUIT_OPEN in types_in_buffer
    
    def test_breaker_emits_on_close(self):
        """熔断器从half_open恢复时emit circuit.close"""
        cb = CircuitBreaker("api", failure_threshold=1, recovery_timeout=0.05)
        
        def fail():
            raise RuntimeError()
        
        def ok():
            return "ok"
        
        with pytest.raises(RuntimeError):
            cb.call(fail)
        assert cb.state == "open"
        
        # 等过恢复期
        import time
        time.sleep(0.1)
        result = cb.call(ok)  # 触发half_open→close
        assert result == "ok"
        assert cb.state == "closed"
        
        from ark.otel_exporter import get_otel_exporter, EventType
        exporter = get_otel_exporter()
        types_in_buffer = [e.event_type for e in exporter._buffer]
        assert EventType.CIRCUIT_HALF_OPEN in types_in_buffer
        assert EventType.CIRCUIT_CLOSE in types_in_buffer
    
    def test_validator_emits_on_fail(self):
        """验证失败时自动emit validation.fail"""
        v = OutputValidator()
        
        class Order(BaseModel):
            order_id: str
            amount: float
        
        result = v.validate(Order, {"order_id": 123, "amount": "bad"})
        assert not result.valid
        
        from ark.otel_exporter import get_otel_exporter, EventType
        exporter = get_otel_exporter()
        types_in_buffer = [e.event_type for e in exporter._buffer]
        assert EventType.VALIDATION_FAIL in types_in_buffer
    
    def test_validator_emits_on_pass(self):
        """验证通过时自动emit validation.pass"""
        v = OutputValidator()
        
        class Order(BaseModel):
            order_id: str
            amount: float
        
        result = v.validate(Order, {"order_id": "o1", "amount": 99.99})
        assert result.valid
        
        from ark.otel_exporter import get_otel_exporter, EventType
        exporter = get_otel_exporter()
        types_in_buffer = [e.event_type for e in exporter._buffer]
        assert EventType.VALIDATION_PASS in types_in_buffer
    
    def test_validator_emits_on_null(self):
        """None输出时也emit validation.fail"""
        v = OutputValidator()
        
        class S(BaseModel):
            x: int
        
        result = v.validate(S, None)
        assert not result.valid
        
        from ark.otel_exporter import get_otel_exporter, EventType
        exporter = get_otel_exporter()
        types_in_buffer = [e.event_type for e in exporter._buffer]
        assert EventType.VALIDATION_FAIL in types_in_buffer
    
    def test_flush_calls_httpx(self):
        """flush时调用httpx.post 发送事件"""
        guard = IdempotencyGuard()
        
        @guard.wrap
        def fn(x: int):
            return x * 2
        
        fn(5)
        
        from ark.otel_exporter import get_otel_exporter
        exporter = get_otel_exporter()
        # 强制 flush
        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200)
            exporter.flush()
            assert mock_post.called
            # 验证 payload 包含 OTLP 结构
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert "resourceSpans" in payload


# ===== Part 3: 性能零开销验证 =====

class TestZeroOverhead:
    """OTel 关闭时性能零影响"""
    
    def setup_method(self):
        os.environ.pop("ARK_OTEL_ENDPOINT", None)
        from ark.otel_exporter import reset_otel_exporter
        reset_otel_exporter()
    
    def teardown_method(self):
        os.environ.pop("ARK_OTEL_ENDPOINT", None)
        from ark.otel_exporter import reset_otel_exporter
        reset_otel_exporter()
    
    def test_no_otel_env_no_lazy_import(self):
        """无ARK_OTEL_ENDPOINT时，_emit_otel 不应触发任何import"""
        # 监控otel_exporter的导入
        import sys
        from ark.guard import _emit_otel
        # 注意：otel_exporter 可能已被其它测试或框架导入过
        # 我们验证 _emit_otel 在 no env 时直接 return
        called = []
        original = sys.modules.get("ark.otel_exporter")
        
        def fake_emit(*a, **kw):
            called.append(1)
        
        # 替换 _emit_otel 的内部分支
        with patch("ark.otel_exporter.get_otel_exporter") as mock_get:
            _emit_otel("ark.test.event", "test_tool", foo="bar")
            # 关键断言：OTel 关闭时，get_otel_exporter 根本没被调用
            mock_get.assert_not_called()
