"""
ARK 熔断控制器 — Sentinel基因移植
工具连续失败→自动熔断→切换备用通道
"""

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

# OTel 集成：函数内读取env，确保"运行时激活"生效


def _emit_otel(event_type: str, tool_name: str, **attrs):
    """内部 helper：OTel 关闭时 zero overhead"""
    if not os.getenv("ARK_OTEL_ENDPOINT", ""):
        return
    try:
        from .otel_exporter import get_otel_exporter, EventType
        et = EventType(event_type)
        get_otel_exporter().emit(et, tool_name=tool_name, attributes=attrs)
    except Exception:
        pass


@dataclass
class CircuitBreaker:
    """熔断控制器：保护Agent不被故障工具拖垮"""
    
    name: str
    failure_threshold: int = 3
    recovery_timeout: float = 30.0
    half_open_max: int = 2
    
    _state: str = field(default="closed", init=False)
    _failure_count: int = field(default=0, init=False)
    _last_failure: float = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _half_open_tries: int = field(default=0, init=False)
    _total_calls: int = field(default=0, init=False)
    _total_failures: int = field(default=0, init=False)
    
    @property
    def state(self) -> str:
        return self._state
    
    def call(self, primary: Callable, fallback: Optional[Callable] = None, *args, **kwargs) -> Any:
        """执行调用，自动熔断+降级"""
        self._total_calls += 1
        
        # 熔断中 → 检查恢复
        if self._state == "open":
            if time.time() - self._last_failure > self.recovery_timeout:
                self._state = "half_open"
                self._half_open_tries = 0
                _emit_otel(
                    "ark.circuit.half_open",
                    tool_name=self.name,
                    recovery_timeout=self.recovery_timeout,
                )
            else:
                if fallback:
                    return fallback(*args, **kwargs)
                raise CircuitOpenError(self.name, self._last_failure)
        
        # 半开 → 谨慎尝试
        if self._state == "half_open":
            self._half_open_tries += 1
            # half_open_max=0 表示不限制半开尝试（边界条件容错）
            if self.half_open_max > 0 and self._half_open_tries > self.half_open_max:
                self._state = "open"
                _emit_otel(
                    "ark.circuit.open",
                    tool_name=self.name,
                    reason="half_open_exhausted",
                    half_open_max=self.half_open_max,
                )
                if fallback:
                    return fallback(*args, **kwargs)
                raise CircuitOpenError(self.name, self._last_failure)
        
        # 尝试执行
        try:
            result = primary(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            self._total_failures += 1
            # 熔断打开时emit事件
            if self._state == "open":
                _emit_otel(
                    "ark.circuit.open",
                    tool_name=self.name,
                    failure_count=self._failure_count,
                    threshold=self.failure_threshold,
                    error=str(e)[:200],
                )
            if fallback:
                return fallback(*args, **kwargs)
            raise
    
    def _on_failure(self):
        prev_state = self._state
        self._failure_count += 1
        self._last_failure = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
            if prev_state != "open":
                _emit_otel(
                    "ark.circuit.open",
                    tool_name=self.name,
                    failure_count=self._failure_count,
                    threshold=self.failure_threshold,
                )
    
    def _on_success(self):
        prev_state = self._state
        if self._state == "half_open":
            self._state = "closed"
            self._failure_count = 0
            _emit_otel(
                "ark.circuit.close",
                tool_name=self.name,
                recovered=True,
            )
        else:
            self._failure_count = 0
            self._success_count += 1
            if prev_state == "closed" and self._total_failures == 0:
                # 长期健康时偶尔emit (噪音控制：仅在事件有语义价值时)
                pass
    
    @property
    def stats(self) -> Dict:
        return {
            "name": self.name,
            "state": self._state,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "total_calls": self._total_calls,
            "total_failures": self._total_failures,
            "reliability": f"{(1 - self._total_failures/max(self._total_calls,1))*100:.1f}%"
        }


class CircuitOpenError(Exception):
    def __init__(self, name: str, last_failure: float):
        wait = max(0, 30 - (time.time() - last_failure))
        super().__init__(f"Circuit {name} is OPEN. Cooldown: {wait:.0f}s")
