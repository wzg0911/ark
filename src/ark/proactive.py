"""
ARK ProactiveGuard — 预测性失败检测
基因来源：memU（意图捕获，⭐13,813）

不再被动等待Agent出错，而是根据模式提前预测潜在失败。
"""

import time, hashlib, json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import wraps


@dataclass
class FailurePattern:
    """失败模式：记录导致失败的参数特征"""
    tool_name: str
    param_signature: str
    failure_count: int = 0
    last_seen: float = field(default_factory=time.time)
    error_samples: List[str] = field(default_factory=list)
    
    def matches(self, args: Dict) -> bool:
        """判断当前调用是否匹配此失败模式"""
        sig = json.dumps(args, sort_keys=True)
        # 精确匹配
        if sig == self.param_signature:
            return True
        # 部分匹配：检查关键参数
        return False
    
    def risk_score(self, recent_failures: int, total_calls: int) -> float:
        """预估风险分数 0-1"""
        if total_calls == 0:
            return 0.0
        freq = self.failure_count / max(total_calls, 1)
        recency = 1.0 / (1.0 + (time.time() - self.last_seen) / 60)
        return min(1.0, freq * 0.7 + recency * 0.3)


@dataclass
class ProactiveGuard:
    """预测性守护者：在Agent出错前预警"""
    
    name: str = "proactive-guard"
    sensitivity: float = 0.3  # 0-1, 越低越敏感（0=阻止一切）, 默认保守值
    history_size: int = 1000
    cooldown_seconds: float = 300.0
    
    _patterns: Dict[str, FailurePattern] = field(default_factory=dict)
    _call_history: List[Dict] = field(default_factory=list)
    _predictions: int = 0
    _correct_predictions: int = 0
    _false_positives: int = 0
    _blocked_calls: int = 0
    _allowed_calls: int = 0
    _total_patterns: int = 0
    
    def record_failure(self, tool_name: str, args: Dict, error: str):
        """记录一次失败，用于模式学习"""
        sig = json.dumps(args, sort_keys=True)
        key = f"{tool_name}::{hashlib.md5(sig.encode()).hexdigest()[:8]}"
        
        if key not in self._patterns:
            self._patterns[key] = FailurePattern(
                tool_name=tool_name,
                param_signature=sig
            )
            self._total_patterns += 1
        
        pattern = self._patterns[key]
        pattern.failure_count += 1
        pattern.last_seen = time.time()
        if len(pattern.error_samples) < 5:
            pattern.error_samples.append(error[:100])
        
        self._call_history.append({
            "timestamp": time.time(),
            "tool": tool_name,
            "args_sig": sig[:20],
            "success": False,
            "error": error[:50]
        })
        self._trim_history()
    
    def record_success(self, tool_name: str, args: Dict):
        """记录一次成功调用"""
        sig = json.dumps(args, sort_keys=True)
        self._call_history.append({
            "timestamp": time.time(),
            "tool": tool_name,
            "args_sig": sig[:20],
            "success": True
        })
        self._trim_history()
    
    def _trim_history(self):
        if len(self._call_history) > self.history_size:
            self._call_history = self._call_history[-self.history_size:]
    
    def predict_risk(self, tool_name: str, args: Dict) -> float:
        """预测执行风险 0-1"""
        sig = json.dumps(args, sort_keys=True)
        key = f"{tool_name}::{hashlib.md5(sig.encode()).hexdigest()[:8]}"
        
        # 1.精确模式匹配
        if key in self._patterns:
            pattern = self._patterns[key]
            recent = sum(1 for c in self._call_history[-20:] 
                        if not c["success"] and c["tool"] == tool_name)
            return pattern.risk_score(recent, len(self._call_history))
        
        # 2.工具级风险分析（同类工具近期失败率）
        recent_calls = [c for c in self._call_history[-50:] if c["tool"] == tool_name]
        if recent_calls:
            fail_rate = sum(1 for c in recent_calls if not c["success"]) / len(recent_calls)
            return fail_rate * 0.5
        
        # 3.未知操作 → 保守估计
        if len(self._call_history) == 0:
            # 无历史数据时风险为0，避免误报已知安全操作
            return 0.0
        
        # 4.全局趋势分析
        recent_calls = self._call_history[-50:]
        recent_fail_rate = sum(1 for c in recent_calls if not c["success"]) / max(len(recent_calls), 1)
        return recent_fail_rate * 0.3
    
    def should_block(self, tool_name: str, args: Dict) -> Tuple[bool, float, str]:
        """判断是否应阻止该调用
        返回：(是否阻止, 风险分数, 原因)
        """
        risk = self.predict_risk(tool_name, args)
        
        if risk >= self.sensitivity:
            self._predictions += 1
            # 找到匹配模式中的错误样例
            sig = json.dumps(args, sort_keys=True)
            key = f"{tool_name}::{hashlib.md5(sig.encode()).hexdigest()[:8]}"
            reason = f"High risk ({risk:.0%}). Previous failures detected."
            if key in self._patterns and self._patterns[key].error_samples:
                reason += f" Example: {self._patterns[key].error_samples[0]}"
            return (True, risk, reason)
        
        return (False, risk, "")
    
    def record_prediction_outcome(self, blocked: bool, succeeded: bool):
        """记录预测结果，用于精度评估"""
        if blocked:
            self._blocked_calls += 1
            # 无法确认被阻止的调用是否会成功，暂记为假阳性
            self._false_positives += 1
        else:
            self._allowed_calls += 1
            if succeeded:
                self._correct_predictions += 1
    
    def wrap(self, tool_func: Callable, tool_name: str = None) -> Callable:
        """包装函数：自动预测+阻止高风险调用"""
        name = tool_name or tool_func.__name__
        
        @wraps(tool_func)
        def wrapper(*args, **kwargs):
            arg_dict = {}
            for i, a in enumerate(args):
                arg_dict[f"arg{i}"] = str(a)
            arg_dict.update(kwargs)
            
            should_block, risk, reason = self.should_block(name, arg_dict)
            
            if should_block and risk >= self.sensitivity:
                self._blocked_calls += 1
                raise ProactiveBlockError(name, risk, reason)
            
            try:
                result = tool_func(*args, **kwargs)
                self.record_success(name, arg_dict)
                self._allowed_calls += 1
                self._correct_predictions += 1
                return result
            except ProactiveBlockError:
                raise
            except Exception as e:
                self.record_failure(name, arg_dict, str(e))
                raise
        
        return wrapper
    
    @property
    def accuracy(self) -> float:
        total = self._correct_predictions + self._false_positives
        if total == 0:
            return 1.0
        return self._correct_predictions / total
    
    @property
    def stats(self) -> Dict:
        return {
            "name": self.name,
            "sensitivity": self.sensitivity,
            "patterns_learned": self._total_patterns,
            "predictions_made": self._predictions,
            "blocked_calls": self._blocked_calls,
            "allowed_calls": self._allowed_calls,
            "accuracy": f"{self.accuracy:.1%}",
            "call_history_size": len(self._call_history),
            "risk_threshold": self.sensitivity,
        }
    
    @property
    def risk_report(self) -> str:
        """生成风险报告文本"""
        lines = [f"🛡 ProactiveGuard: {self.name}",
                 f"   Patterns: {self._total_patterns} | Blocked: {self._blocked_calls} | Acc: {self.accuracy:.1%}"]
        
        # 显示Top风险模式
        if self._patterns:
            sorted_patterns = sorted(
                self._patterns.values(),
                key=lambda p: p.failure_count,
                reverse=True
            )[:5]
            lines.append("   Top Risk Patterns:")
            for p in sorted_patterns:
                lines.append(f"     ⚠ {p.tool_name} (×{p.failure_count}) {p.error_samples[0][:60] if p.error_samples else ''}")
        
        return "\n".join(lines)


class ProactiveBlockError(Exception):
    """被预测性守卫阻止的调用错误"""
    def __init__(self, tool_name: str, risk: float, reason: str):
        super().__init__(
            f"ARK ProactiveGuard blocked [{tool_name}]. "
            f"Risk: {risk:.0%}. {reason}"
        )
        self.tool_name = tool_name
        self.risk = risk
