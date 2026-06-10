"""
ARK 幂等守护 — Stripe基因移植
防止Agent重复执行工具调用（付款、发邮件、调API）
加锁：线程安全并发幂等
"""

import hashlib, json, time, threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from functools import wraps


@dataclass
class ExecutionRecord:
    idempotency_key: str
    tool_name: str
    args_hash: str
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    timestamp: float = field(default_factory=time.time)


class IdempotencyGuard:
    """幂等守护：每个工具调用生成唯一Key，重复自动拦截"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._executed: Dict[str, ExecutionRecord] = {}
        self._ttl = ttl_seconds
        self._lock = threading.RLock()
        self.intercepts = 0
        self.passes = 0
    
    def key(self, tool_name: str, args: Dict) -> str:
        """生成幂等Key"""
        payload = json.dumps({"tool": tool_name, "args": args}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
    
    def check(self, key: str) -> Optional[ExecutionRecord]:
        """检查是否已执行，已执行返回记录"""
        with self._lock:
            if key in self._executed:
                record = self._executed[key]
                if time.time() - record.timestamp < self._ttl:
                    return record
                del self._executed[key]
            return None
    
    def record(self, key: str, record: ExecutionRecord):
        with self._lock:
            self._executed[key] = record
    
    def wrap(self, tool_func, tool_name: str = None):
        """装饰器：包装任意工具函数"""
        name = tool_name or tool_func.__name__
        
        @wraps(tool_func)
        def wrapper(*args, **kwargs):
            # 转换为dict以生成幂等key
            arg_dict = {}
            if args:
                for i, a in enumerate(args):
                    arg_dict[f"arg{i}"] = str(a)
            arg_dict.update(kwargs)
            
            key = self.key(name, arg_dict)
            
            # 幂等检查（锁内原子操作）
            cached = self.check(key)
            if cached:
                self.intercepts += 1
                if cached.error:
                    raise RuntimeError(f"ARK Cached failure [{name}]: {cached.error}")
                return cached.result
            
            # 抢占锁：标记正在执行，防止并发
            # 先写入临时记录
            temp_record = ExecutionRecord(
                idempotency_key=key,
                tool_name=name,
                args_hash=hashlib.md5(json.dumps(arg_dict, sort_keys=True).encode()).hexdigest()[:8]
            )
            with self._lock:
                # 双重检查
                if key in self._executed:
                    cached = self._executed[key]
                    if time.time() - cached.timestamp < self._ttl:
                        self.intercepts += 1
                        if cached.error:
                            raise RuntimeError(f"ARK Cached failure [{name}]: {cached.error}")
                        return cached.result
                # 设置执行标记
                self._executed[key] = temp_record
            
            # 真正执行
            start = time.time()
            record = temp_record
            
            try:
                result = tool_func(*args, **kwargs)
                record.result = result
                record.duration_ms = (time.time() - start) * 1000
                
                with self._lock:
                    self._executed[key] = record
                self.passes += 1
                return result
            except Exception as e:
                record.error = str(e)
                record.duration_ms = (time.time() - start) * 1000
                with self._lock:
                    self._executed[key] = record
                raise
        
        return wrapper
    
    @property
    def stats(self) -> Dict:
        total = self.intercepts + self.passes
        return {
            "total_records": len(self._executed),
            "intercepts": self.intercepts,
            "passes": self.passes,
            "save_rate": f"{self.intercepts/total*100:.1f}%" if total > 0 else "0%"
        }
