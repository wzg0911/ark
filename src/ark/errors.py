"""
ARK Error Compressor — F9: 把错误压缩进上下文
基因来源：12-Factor Agents (HumanLayer) Factor 9

🎯 三个核心能力：
1. **truncate_error()** — 把 stack trace 截断到 500 字符（保留最后 3 行）
2. **to_llm_context()** — 把错误结构化喂给 LLM（让 Agent 自愈）
3. **should_retry()** — 重试判断器（指数退避 + 重试上限 + 升级路径）

设计原则：
- 零依赖（不依赖 LLM 库，只依赖 stdlib）
- 零开销（不调用时无影响）
- 可序列化（错误 → dict → JSON → LLM context）
- 12-Factor 自检：F9 ✅ 错误有截断、有重试上限、有升级路径
"""

import hashlib
import time
import traceback
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# ━━━━━━━━━━ 1. 错误截断（truncate_error）━━━━━━━━━━

def truncate_error(
    exception: BaseException,
    max_message_length: int = 500,
    max_stack_lines: int = 3,
) -> Dict[str, Any]:
    """
    F9 核心：截断错误到 LLM 友好的格式
    
    关键技巧：
    - error_message 截断到 500 字符
    - stack_trace 只保留最后 3 行（最相关）
    - 不重复"Exception"头部
    """
    full_message = str(exception)
    truncated_message = (
        full_message[:max_message_length]
        + ("..." if len(full_message) > max_message_length else "")
    )
    
    full_stack = traceback.format_exc().split('\n')
    # 取最后 N 行（Python traceback 倒序有意义：先错后行号）
    tail_lines = [line for line in full_stack if line.strip()][-max_stack_lines:]
    
    return {
        "type": type(exception).__name__,
        "message": truncated_message,
        "stack_tail": tail_lines,
        "raw_hash": hashlib.md5(full_message.encode("utf-8")).hexdigest()[:8],
    }


# ━━━━━━━━━━ 2. 喂给 LLM 的格式（to_llm_context）━━━━━━━━━━

def error_to_llm_context(
    exception: BaseException,
    tool_name: str,
    attempt: int,
    previous_attempts: Optional[List[Dict]] = None,
) -> str:
    """
    F9 + F3 联动：把错误结构化成 LLM 友好的 context 段落
    
    设计：给 LLM 看的，不是给人看的
    - 简短（< 200 token）
    - 明确：出什么错 + 在哪个工具 + 第几次尝试
    - 自愈引导：给 LLM 一个"该换个思路"的暗示
    """
    err = truncate_error(exception)
    
    lines = [
        f"[ERROR] Tool `{tool_name}` failed (attempt {attempt})",
        f"Type:    {err['type']}",
        f"Message: {err['message']}",
    ]
    
    if err["stack_tail"]:
        lines.append("Stack (last lines):")
        for stack_line in err["stack_tail"]:
            lines.append(f"  {stack_line.strip()}")
    
    # 自愈引导 — 第二次失败时提示 LLM 该换思路
    if attempt >= 2:
        lines.append("")
        lines.append("💡 Hint: This is a repeat failure. Consider:")
        lines.append("  - Different tool / approach")
        lines.append("  - Different input parameters")
        lines.append("  - Check input format / types")
        if attempt >= 3:
            lines.append("  - Escalate to human if critical")
    
    # 历史尝试 — 让 LLM 看到重复模式
    if previous_attempts:
        lines.append("")
        lines.append(f"Previous attempts ({len(previous_attempts)}):")
        for i, prev in enumerate(previous_attempts[-3:], 1):  # 最多展示 3 次
            lines.append(
                f"  {i}. [{prev.get('type', 'Unknown')}] {prev.get('message', '')[:200]}"
            )
    
    return "\n".join(lines)


# ━━━━━━━━━━ 3. 重试判断器（should_retry）━━━━━━━━━━

# 不可重试的错误类型（立即升级给人类）
NON_RETRYABLE_TYPES = {
    "AuthenticationError",  # 认证失败，重试无用
    "PermissionError",       # 权限不足
    "ValidationError",       # 输入验证失败（修了输入再重试，不是修工具）
    "NotImplementedError",   # 功能未实现
    "SyntaxError",           # 代码错误
    "ImportError",           # 模块缺失
    "ModuleNotFoundError",
    "KeyboardInterrupt",     # 用户中断
}


def should_retry(
    exception: BaseException,
    attempt: int,
    max_attempts: int = 3,
) -> bool:
    """
    F9 重试判断器
    
    规则：
    - attempt < max_attempts → 可重试
    - 不可重试的错误类型 → 立即停止
    - 超过上限 → 升级给人类
    """
    if attempt >= max_attempts:
        return False
    if type(exception).__name__ in NON_RETRYABLE_TYPES:
        return False
    return True


def retry_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    backoff_factor: float = 2.0,
) -> float:
    """
    F9 指数退避：1s, 2s, 4s, 8s, 16s, capped at 30s
    """
    delay = base_delay * (backoff_factor ** (attempt - 1))
    return min(delay, max_delay)


# ━━━━━━━━━━ 4. ErrorContext 累加器（Thread-safe）━━━━━━━━━━

@dataclass
class ErrorContext:
    """
    F9 + F5 联动：把错误事件作为 Thread 的一部分持久化
    
    设计：
    - 每次失败 = 一个 ErrorRecord
    - 可以序列化进 JSON 状态
    - LLM 可以在 Thread 末尾看到完整失败历史
    """
    tool_name: str
    max_attempts: int = 3
    records: List[Dict] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)
    
    def record_failure(
        self,
        exception: BaseException,
        attempt: int,
    ) -> Dict:
        """记录一次失败（不抛异常，纯记录）"""
        err = truncate_error(exception)
        record = {
            "type": err["type"],
            "message": err["message"],
            "stack_tail": err["stack_tail"],
            "attempt": attempt,
            "timestamp": time.time(),
            "retryable": should_retry(exception, attempt, self.max_attempts),
        }
        self.records.append(record)
        return record
    
    @property
    def failure_count(self) -> int:
        return len(self.records)
    
    @property
    def last_error(self) -> Optional[Dict]:
        return self.records[-1] if self.records else None
    
    @property
    def should_escalate(self) -> bool:
        """
        F9 升级条件：
        - 达到 max_attempts
        - 遇到不可重试的错误
        """
        if not self.records:
            return False
        last = self.records[-1]
        return not last["retryable"] or last["attempt"] >= self.max_attempts
    
    def to_llm_context(self) -> str:
        """整个错误上下文喂给 LLM"""
        if not self.records:
            return ""
        
        lines = [
            f"[ERROR CONTEXT] Tool `{self.tool_name}` has {self.failure_count} failure(s)",
            "",
        ]
        
        for rec in self.records:
            lines.append(f"[ERROR] Tool `{self.tool_name}` failed (attempt {rec['attempt']})")
            lines.append(f"Type:    {rec['type']}")
            lines.append(f"Message: {rec['message']}")
            if rec.get("stack_tail"):
                lines.append("Stack (last lines):")
                for stack_line in rec["stack_tail"]:
                    if stack_line and stack_line.strip():
                        lines.append(f"  {stack_line.strip()}")
            if rec["attempt"] >= 2:
                lines.append("")
                lines.append("💡 Hint: This is a repeat failure. Consider:")
                lines.append("  - Different tool / approach")
                lines.append("  - Different input parameters")
                lines.append("  - Check input format / types")
                if rec["attempt"] >= 3:
                    lines.append("  - Escalate to human if critical")
            lines.append("")
        
        if self.should_escalate:
            lines.append("🚨 ESCALATE TO HUMAN: This tool has failed too many times.")
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict:
        """可序列化（F5 状态统一）"""
        return {
            "tool_name": self.tool_name,
            "max_attempts": self.max_attempts,
            "records": self.records,
            "started_at": self.started_at,
            "failure_count": self.failure_count,
            "should_escalate": self.should_escalate,
        }


class _FakeException(BaseException):
    """仅用于从 record 重建异常对象（喂给 to_llm_context）"""
    def __init__(self, type_name: str, message: str):
        self.type_name = type_name
        self.message = message
        super().__init__(message)


# ━━━━━━━━━━ 5. 整合 helper：with_retry 装饰器 + 上下文管理器 ━━━━━━━━━━

import logging
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def error_context(
    tool_name: str,
    max_attempts: int = 3,
    on_retry: Optional[Any] = None,  # Callable[[int, float], None]
):
    """
    F9 上下文管理器：在 with 块内自动捕获错误并喂给 LLM context
    
    用法：
        with error_context("create_payment_link", max_attempts=3) as ctx:
            result = stripe.paymentlinks.create(...)
            # 如果失败：自动记录 + 重试判断 + 升级路径
    """
    ctx = ErrorContext(tool_name=tool_name, max_attempts=max_attempts)
    try:
        yield ctx
    except Exception as e:
        # 只记录一次失败 (重试逻辑由调用方/装饰器负责)
        ctx.record_failure(e, attempt=1)
        if ctx.should_escalate:
            logger.error(
                f"[{tool_name}] F9 ESCALATE: {e.__class__.__name__}: {str(e)[:200]}"
            )


def with_retry(
    tool_name: Optional[str] = None,
    max_attempts: int = 3,
    fallback: Optional[Any] = None,
):
    """
    F9 装饰器：包装函数，自动重试 + 错误截断 + 升级路径
    
    用法：
        @with_retry(tool_name="send_email", max_attempts=3)
        def send_email(to: str, subject: str):
            return smtp.send(to, subject)
    """
    def decorator(func):
        name = tool_name or func.__name__
        ctx = ErrorContext(tool_name=name, max_attempts=max_attempts)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 1:
                        logger.info(f"[{name}] F9 RECOVERED on attempt {attempt}")
                    return result
                except Exception as e:
                    ctx.record_failure(e, attempt)
                    if not should_retry(e, attempt, max_attempts):
                        # 不可重试 / 达上限：使用 fallback 或包装后抛出
                        logger.error(
                            f"[{name}] F9 ESCALATE: {e.__class__.__name__}: {str(e)[:200]}"
                        )
                        if fallback is not None:
                            return fallback(*args, **kwargs)
                        if attempt >= max_attempts:
                            # 重试上限：包装为 RuntimeError
                            raise RuntimeError(
                                f"[{name}] All {max_attempts} attempts failed. "
                                f"Last error: {type(e).__name__}: {str(e)[:200]}"
                            ) from e
                        # 不可重试错误：透传原异常
                        raise
                    delay = retry_delay(attempt)
                    logger.warning(
                        f"[{name}] F9 RETRY {attempt}/{max_attempts} after {delay:.1f}s: "
                        f"{e.__class__.__name__}"
                    )
                    time.sleep(delay)
            
            # 理论不可达
            raise RuntimeError(f"[{name}] Unexpected: loop ended without return")
        
        # 暴露 ctx 给调用方（用于 LLM 上下文）
        wrapper.error_context = ctx
        return wrapper
    
    return decorator


# ━━━━━━━━━━ 公开 API ━━━━━━━━━━

__all__ = [
    "truncate_error",
    "error_to_llm_context",
    "should_retry",
    "retry_delay",
    "NON_RETRYABLE_TYPES",
    "ErrorContext",
    "error_context",
    "with_retry",
]
