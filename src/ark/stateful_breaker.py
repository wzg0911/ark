"""
ARK StatefulBreaker — 状态持久化熔断器
基因来源：EverOS (⭐7,225) + MemBrain (记忆大脑)

熔断状态持久化到JSON文件，Agent重启后不丢失熔断状态。
"""

import os, json, time, threading
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, Optional, List


@dataclass
class BreakerSnapshot:
    """熔断器状态快照（字段名与内部属性一致）"""
    name: str
    _state: str
    _failure_count: int
    _last_failure: float
    _success_count: int
    _half_open_tries: int
    _total_calls: int
    _total_failures: int
    updated_at: float


class StatefulBreaker:
    """持久化熔断器：重启不丢失状态"""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        half_open_max: int = 2,
        persist_path: Optional[str] = None,
        auto_persist: bool = True
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max = half_open_max
        self.auto_persist = auto_persist
        
        # 持久化路径
        if persist_path:
            self._persist_path = persist_path
        else:
            ark_dir = os.path.expanduser("~/.ark/state")
            os.makedirs(ark_dir, exist_ok=True)
            self._persist_path = os.path.join(ark_dir, f"breaker_{name}.json")
        
        # 加载持久化状态
        self._lock = threading.RLock()
        self._load_state()
        # 触发一次持久化，确保文件创建（即使没有调用过）
        self._save_state()
    
    def _default_state(self) -> Dict:
        return {
            "name": self.name,
            "_state": "closed",
            "_failure_count": 0,
            "_last_failure": 0.0,
            "_success_count": 0,
            "_half_open_tries": 0,
            "_total_calls": 0,
            "_total_failures": 0,
        }
    
    def _load_state(self):
        """从JSON文件加载持久化状态"""
        defaults = self._default_state()
        if os.path.exists(self._persist_path):
            try:
                with open(self._persist_path, "r") as f:
                    data = json.load(f)
                for k, v in data.items():
                    defaults[k] = v
            except (json.JSONDecodeError, IOError):
                pass
        
        self._state = defaults["_state"]
        self._failure_count = defaults["_failure_count"]
        self._last_failure = defaults["_last_failure"]
        self._success_count = defaults["_success_count"]
        self._half_open_tries = defaults["_half_open_tries"]
        self._total_calls = defaults["_total_calls"]
        self._total_failures = defaults["_total_failures"]
    
    def _save_state(self):
        """保存状态到JSON文件"""
        if not self.auto_persist:
            return
        snapshot = BreakerSnapshot(
            name=self.name,
            _state=self._state,
            _failure_count=self._failure_count,
            _last_failure=self._last_failure,
            _success_count=self._success_count,
            _half_open_tries=self._half_open_tries,
            _total_calls=self._total_calls,
            _total_failures=self._total_failures,
            updated_at=time.time()
        )
        try:
            with open(self._persist_path, "w") as f:
                json.dump(asdict(snapshot), f, indent=2)
        except IOError:
            pass
    
    @property
    def state(self) -> str:
        return self._state
    
    def call(self, primary: Callable, fallback: Optional[Callable] = None, *args, **kwargs) -> Any:
        """执行调用，自动熔断+降级"""
        with self._lock:
            self._total_calls += 1
            
            # 熔断中 → 检查恢复
            if self._state == "open":
                if time.time() - self._last_failure > self.recovery_timeout:
                    self._state = "half_open"
                    self._half_open_tries = 0
                    self._save_state()
                else:
                    remaining = self.recovery_timeout - (time.time() - self._last_failure)
                    if fallback:
                        return fallback(*args, **kwargs)
                    raise CircuitOpenError(self.name, remaining)
            
            # 半开 → 谨慎尝试
            if self._state == "half_open":
                self._half_open_tries += 1
                if self._half_open_tries > self.half_open_max:
                    self._state = "open"
                    self._save_state()
                    if fallback:
                        return fallback(*args, **kwargs)
                    raise CircuitOpenError(self.name, self.recovery_timeout)
        
        # 尝试执行（锁外，避免长操作卡锁）
        try:
            result = primary(*args, **kwargs)
            with self._lock:
                self._on_success()
                self._save_state()
            return result
        except Exception as e:
            with self._lock:
                self._on_failure()
                self._total_failures += 1
                self._save_state()
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
    
    def reset(self):
        """手动重置熔断器"""
        with self._lock:
            defaults = self._default_state()
            for k, v in defaults.items():
                setattr(self, k, v)
            self._save_state()
    
    def inspect_persistence(self) -> Dict:
        """检查持久化状态"""
        result = {
            "persist_path": self._persist_path,
            "file_exists": os.path.exists(self._persist_path),
            "current_state": self._state,
        }
        if result["file_exists"]:
            try:
                with open(self._persist_path, "r") as f:
                    result["stored_data"] = json.load(f)
            except:
                result["stored_data"] = None
        return result
    
    @property
    def stats(self) -> Dict:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_calls": self._total_calls,
                "total_failures": self._total_failures,
                "recovery_timeout": self.recovery_timeout,
                "persist_path": self._persist_path,
                "reliability": f"{(1 - self._total_failures/max(self._total_calls,1))*100:.1f}%",
            }


class CircuitOpenError(Exception):
    def __init__(self, name: str, wait: float):
        super().__init__(f"Circuit [{name}] OPEN. Cooldown: {max(0, wait):.0f}s")
