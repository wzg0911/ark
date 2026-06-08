"""
ARK 链路追踪 — OpenTelemetry基因移植
Agent每一步→Span→可追溯→可回放
"""

import time, uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._trace is not None:
            error = str(exc_val) if exc_val else None
            self._trace.end_span(error=error)
        return False

class Trace:
    """链路追踪：看见Agent的完整执行路径"""
    
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
    
    def end_span(self, error: str = None, **attrs):
        if len(self._stack) > 1:
            span = self._stack.pop()
            span.end_time = time.time()
            span.attributes.update(attrs)
            if error:
                span.status = "error"
                span.error = error
            else:
                span.status = "ok"
    
    @property
    def duration_ms(self) -> float:
        return (time.time() - self.root.start_time) * 1000
    
    def summary(self) -> Dict:
        errors = self._count_errors(self.root)
        return {
            "trace_id": self.trace_id,
            "total_spans": self.total_spans,
            "duration_ms": self.duration_ms,
            "errors": errors,
            "status": "error" if errors > 0 else "ok"
        }
    
    def _count_errors(self, span: Span) -> int:
        count = 1 if span.status == "error" else 0
        for child in span.children:
            count += self._count_errors(child)
        return count
    
    def tree(self) -> str:
        return self._render(self.root, 0)
    
    def _render(self, span: Span, depth: int) -> str:
        lines = ["  " * depth + f"{'❌' if span.status=='error' else '✅' if span.status=='ok' else '⏳'} {span.name} ({span.span_id})"]
        if span.error:
            lines[-1] += f" — {span.error[:50]}"
        for child in span.children:
            lines.append(self._render(child, depth + 1))
        return "\n".join(lines)
