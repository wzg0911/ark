"""
ARK ModuleKit — 可组合可靠性模块
基因来源：GenericAgent（模块化能力魔方）+ nuwa-skill（认知蒸馏）

极简能力模块→组合为任意可靠性管道。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Type
from functools import wraps
import time, json


@dataclass
class Module:
    """可靠性模块基类"""
    name: str = ""
    enabled: bool = True
    priority: int = 100  # 越小越先执行
    
    def process(self, tool_name: str, args: Dict, context: Dict) -> Dict:
        """处理一次工具调用
        返回：{
            "action": "allow" | "block" | "warn",
            "reason": str,
            "context": Dict (传递给下一模块)
        }
        """
        return {"action": "allow", "reason": "", "context": context}
    
    @property
    def stats(self) -> Dict:
        return {"name": self.name, "enabled": self.enabled}


@dataclass
class ModulePipeline:
    """模块管道——按优先级串联多个可靠性模块"""
    name: str = "default-pipeline"
    modules: List[Module] = field(default_factory=list)
    _total_calls: int = 0
    _blocked_calls: int = 0
    _allowed_calls: int = 0
    
    def add(self, module: Module) -> "ModulePipeline":
        """添加模块到管道"""
        self.modules.append(module)
        self.modules.sort(key=lambda m: m.priority)
        return self
    
    def remove(self, module_name: str) -> bool:
        """移除模块"""
        for i, m in enumerate(self.modules):
            if m.name == module_name:
                self.modules.pop(i)
                return True
        return False
    
    def process(self, tool_name: str, args: Dict) -> Dict:
        """通过管道处理一次工具调用"""
        self._total_calls += 1
        context = {}
        
        for module in self.modules:
            if not module.enabled:
                continue
            result = module.process(tool_name, args, context)
            context.update(result.get("context", {}))
            
            if result["action"] == "block":
                self._blocked_calls += 1
                return {
                    "action": "block",
                    "reason": f"[{module.name}] {result['reason']}",
                    "context": context
                }
            elif result["action"] == "warn":
                context["warnings"] = context.get("warnings", []) + [result["reason"]]
        
        self._allowed_calls += 1
        return {"action": "allow", "reason": "", "context": context}
    
    def wrap(self, tool_func: Callable, tool_name: str = None) -> Callable:
        """包装函数——通过管道过滤"""
        name = tool_name or tool_func.__name__
        
        @wraps(tool_func)
        def wrapper(*args, **kwargs):
            arg_dict = {}
            for i, a in enumerate(args):
                arg_dict[f"arg{i}"] = str(a)
            arg_dict.update(kwargs)
            
            result = self.process(name, arg_dict)
            if result["action"] == "block":
                raise ModuleBlockError(name, result["reason"])
            
            return tool_func(*args, **kwargs)
        
        return wrapper
    
    @property
    def stats(self) -> Dict:
        return {
            "name": self.name,
            "modules": len(self.modules),
            "total_calls": self._total_calls,
            "blocked": self._blocked_calls,
            "allowed": self._allowed_calls,
            "block_rate": f"{self._blocked_calls/max(self._total_calls,1)*100:.1f}%",
            "module_list": [m.name for m in self.modules],
        }


# ─── 预置模块 ───

@dataclass
class RateLimitModule(Module):
    """速率限制模块"""
    max_calls_per_minute: int = 60
    _call_timestamps: List[float] = field(default_factory=list)
    _blocked: int = 0
    _passed: int = 0
    
    def __post_init__(self):
        self.name = f"rate-limit-{self.max_calls_per_minute}pm"
    
    def process(self, tool_name: str, args: Dict, context: Dict) -> Dict:
        now = time.time()
        self._call_timestamps = [t for t in self._call_timestamps if now - t < 60]
        
        if len(self._call_timestamps) >= self.max_calls_per_minute:
            self._blocked += 1
            return {
                "action": "block",
                "reason": f"Rate limit: {self.max_calls_per_minute}/min exceeded",
                "context": context
            }
        
        self._call_timestamps.append(now)
        self._passed += 1
        return {"action": "allow", "reason": "", "context": context}
    
    @property
    def stats(self) -> Dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "limit": f"{self.max_calls_per_minute}/min",
            "blocked": self._blocked,
            "passed": self._passed,
            "active_in_window": len(self._call_timestamps),
        }


@dataclass
class SchemaValidationModule(Module):
    """Schema验证模块"""
    schema: Optional[Type] = None
    _validated: int = 0
    _failed: int = 0
    
    def __post_init__(self):
        self.name = "schema-validation"
    
    def process(self, tool_name: str, args: Dict, context: Dict) -> Dict:
        if not self.schema:
            return {"action": "allow", "reason": "", "context": context}
        
        try:
            instance = self.schema(**args)
            self._validated += 1
            return {"action": "allow", "reason": "", "context": context}
        except Exception as e:
            self._failed += 1
            return {
                "action": "block",
                "reason": f"Schema validation failed: {str(e)[:100]}",
                "context": context
            }
    
    @property
    def stats(self) -> Dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "validated": self._validated,
            "failed": self._failed,
        }


@dataclass
class LoggingModule(Module):
    """日志记录模块"""
    _log: List[Dict] = field(default_factory=list)
    max_log_size: int = 1000
    
    def __post_init__(self):
        self.name = "logging"
        self.priority = 999  # 最后执行
    
    def process(self, tool_name: str, args: Dict, context: Dict) -> Dict:
        entry = {
            "timestamp": time.time(),
            "tool": tool_name,
            "args_keys": list(args.keys()),
            "warnings": context.get("warnings", []),
        }
        self._log.append(entry)
        if len(self._log) > self.max_log_size:
            self._log = self._log[-self.max_log_size:]
        return {"action": "allow", "reason": "", "context": context}
    
    @property
    def stats(self) -> Dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "log_size": len(self._log),
        }


class ModuleBlockError(Exception):
    def __init__(self, tool_name: str, reason: str):
        super().__init__(f"ARK ModulePipe blocked [{tool_name}]: {reason}")
