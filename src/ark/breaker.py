"""
ARK 熔断控制器 — Sentinel基因移植
工具连续失败→自动熔断→切换备用通道
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

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
            else:
                if fallback:
                    return fallback(*args, **kwargs)
                raise CircuitOpenError(self.name, self._last_failure)
        
        # 半开 → 谨慎尝试
        if self._state == "half_open":
            self._half_open_tries += 1
            if self._half_open_tries > self.half_open_max:
                self._state = "open"
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
            if fallback:
                return fallback(*args, **kwargs)
            raise
    
    def _on_failure(self):
        self._failure_count += 1
        self._last_failure = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = "open"
    
    def _on_success(self):
        if self._state == "half_open":
            self._state = "closed"
        self._failure_count = 0
        self._success_count += 1
    
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
