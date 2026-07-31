"""
ARK 链路追踪 — OpenTelemetry基因移植
Agent每一步→Span→可追溯→可回放

终态不变式（Terminal-state invariant, v0.8.1）
--------------------------------------------
每一个 started 的 span 必须恰好到达一个终态：
    ok | error | cancelled | orphaned

这是 ARK 对 langchain-core#39163（F3 族第 5 例「终态事件缺失」）开出的处方，
在 ARK 自身实现上先行落地：

1. `except Exception` 是错的 —— `asyncio.CancelledError` / `KeyboardInterrupt`
   继承自 `BaseException`，不能靠捕获 `Exception` 兜住。Span 上下文管理器按
   `BaseException` 处理退出。
2. `cancelled` 是**独立终态**，不是 error —— 客户端断连（ASGI/WebSocket 常态）
   不应污染失败率，但必须留痕。
3. `summary()` 必须能区分「真实的长任务」与「孤儿 span」—— 未闭合的 span 在
   汇总时被标记为 `orphaned`，且 trace 状态不得报 `ok`。
"""

import time, uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

#: 合法终态集合（started span 必须恰好落入其一）
TERMINAL_STATES = ("ok", "error", "cancelled", "orphaned")

#: 视为「取消」而非「失败」的异常类型
_CANCELLATION_EXC = (KeyboardInterrupt, SystemExit)
try:  # asyncio 始终可用，防御式导入仅为极端裁剪环境
    import asyncio as _asyncio

    _CANCELLATION_EXC = _CANCELLATION_EXC + (_asyncio.CancelledError,)
except Exception:  # pragma: no cover
    pass


def _is_cancellation(exc: BaseException) -> bool:
    """判定异常是否属于「取消」语义（独立终态，不计失败）。"""
    return isinstance(exc, _CANCELLATION_EXC)


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    parent_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    attributes: Dict = field(default_factory=dict)
    status: str = "running"
    error: Optional[str] = None
    children: List["Span"] = field(default_factory=list)
    _trace: Optional["Trace"] = field(default=None, repr=False)

    @property
    def is_terminal(self) -> bool:
        """是否已到达终态。"""
        return self.status in TERMINAL_STATES

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 关键：不得写成 `except Exception` 语义。BaseException（CancelledError /
        # KeyboardInterrupt）同样必须触发终态回调，否则 span 永久 pending。
        if self._trace is not None:
            if exc_val is not None and _is_cancellation(exc_val):
                self._trace.end_span(
                    cancelled=True,
                    error=str(exc_val) or exc_type.__name__ if exc_type else None,
                )
            else:
                error = str(exc_val) if exc_val is not None else None
                self._trace.end_span(error=error)
        return False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


class Trace:
    """链路追踪：看见Agent的完整执行路径（含终态不变式强制）"""

    def __init__(self, name: str = "agent-execution"):
        self.trace_id = uuid.uuid4().hex[:12]
        self.root = Span(name=name, trace_id=self.trace_id)
        self._stack = [self.root]
        self.total_spans = 1

    def start_span(self, name: str, **attrs) -> Span:
        parent = self._stack[-1]
        span = Span(
            name=name,
            trace_id=self.trace_id,
            parent_id=parent.span_id,
            attributes=attrs
        )
        parent.children.append(span)
        self._stack.append(span)
        self.total_spans += 1
        span._trace = self
        return span

    def end_span(self, error: str = None, cancelled: bool = False, **attrs):
        """关闭当前 span。

        Args:
            error: 错误摘要；非空且未标记 cancelled 时终态为 ``error``。
            cancelled: 标记为取消终态（``cancelled``），**不计入 errors**，
                但仍写入 ``error`` 字段留痕，供成本/延迟归因使用。
        """
        if len(self._stack) > 1:
            span = self._stack.pop()
            span.end_time = time.time()
            span.attributes.update(attrs)
            if cancelled:
                span.status = "cancelled"
                span.error = error
            elif error:
                span.status = "error"
                span.error = error
            else:
                span.status = "ok"

    def close(self, error: str = None, cancelled: bool = False):
        """收敛整条 trace：未闭合的子 span 标记为 ``orphaned``，root 落终态。

        这是「终态存在性」校验点 —— 对应 ARK 对 #39163 的处方：
        span 退出而无终态，则自动补发 orphaned 而不是静默留 pending。
        """
        orphaned = 0
        while len(self._stack) > 1:
            span = self._stack.pop()
            span.end_time = time.time()
            span.status = "orphaned"
            if span.error is None:
                span.error = "span exited without terminal state"
            orphaned += 1

        if self.root.status == "running":
            self.root.end_time = time.time()
            if cancelled:
                self.root.status = "cancelled"
                self.root.error = error
            elif error:
                self.root.status = "error"
                self.root.error = error
            else:
                self.root.status = "ok"
        return orphaned

    @property
    def duration_ms(self) -> float:
        return (time.time() - self.root.start_time) * 1000

    def summary(self) -> Dict:
        errors = self._count(self.root, "error")
        cancelled = self._count(self.root, "cancelled")
        # root 本身尚未 close 时不算孤儿；只统计「已 start 未 end 的子 span」
        pending = self._count_pending(self.root)
        orphaned = self._count(self.root, "orphaned") + pending

        if errors > 0:
            status = "error"
        elif orphaned > 0:
            # 关键不变式：存在无终态的 span 时，绝不报 ok
            status = "incomplete"
        elif cancelled > 0:
            status = "cancelled"
        else:
            status = "ok"

        return {
            "trace_id": self.trace_id,
            "total_spans": self.total_spans,
            "duration_ms": self.duration_ms,
            "errors": errors,
            "cancelled": cancelled,
            "orphaned": orphaned,
            "status": status,
        }

    def assert_terminal(self) -> List[str]:
        """返回所有未到达终态的 span 名称（空列表 = 不变式成立）。"""
        missing: List[str] = []
        self._collect_pending(self.root, missing, is_root=True)
        return missing

    def _collect_pending(self, span: "Span", out: List[str], is_root: bool = False):
        if not is_root and span.status == "running":
            out.append(f"{span.name}({span.span_id})")
        for child in span.children:
            self._collect_pending(child, out)

    def _count(self, span: "Span", status: str) -> int:
        count = 1 if span.status == status else 0
        for child in span.children:
            count += self._count(child, status)
        return count

    def _count_pending(self, span: "Span", is_root: bool = True) -> int:
        count = 0 if is_root else (1 if span.status == "running" else 0)
        for child in span.children:
            count += self._count_pending(child, is_root=False)
        return count

    def _count_errors(self, span: "Span") -> int:
        """向后兼容保留：仅统计 error 终态。"""
        return self._count(span, "error")

    def tree(self) -> str:
        return self._render(self.root, 0)

    _ICONS = {
        "error": "❌",
        "ok": "✅",
        "cancelled": "🚫",
        "orphaned": "👻",
        "running": "⏳",
    }

    def _render(self, span: "Span", depth: int) -> str:
        icon = self._ICONS.get(span.status, "⏳")
        lines = ["  " * depth + f"{icon} {span.name} ({span.span_id})"]
        if span.error:
            lines[-1] += f" — {span.error[:50]}"
        for child in span.children:
            lines.append(self._render(child, depth + 1))
        return "\n".join(lines)
