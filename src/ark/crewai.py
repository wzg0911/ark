"""
ARK × CrewAI Integration
Drop-in reliability layer for CrewAI agents.

Usage:
    from ark.crewai import ARKCrewCallback
    from crewai import Agent, Task, Crew
    
    agent = Agent(role="...", goal="...")
    crew = Crew(agents=[agent], tasks=[task])
    crew.callback = ARKCrewCallback()
"""

import time
from typing import Any, Dict, Optional

try:
    from crewai.crew import Crew
    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False

from ..guard import IdempotencyGuard
from ..breaker import CircuitBreaker
from ..validator import OutputValidator
from ..trace import Trace


class ARKCrewCallback:
    """ARK信任层 × CrewAI
    
    接入方式：
    >>> crew = Crew(agents=[agent], tasks=[task])
    >>> handler = ARKCrewCallback()
    >>> result = crew.kickoff(inputs={"topic": "..."}, callbacks=handler)
    >>> print(handler.report)
    """
    
    def __init__(self, idempotency_ttl: int = 3600, circuit_failures: int = 3):
        self.guard = IdempotencyGuard(ttl_seconds=idempotency_ttl)
        self.breaker = CircuitBreaker("crewai-agent", failure_threshold=circuit_failures)
        self.validator = OutputValidator()
        self.trace = Trace("crew-mission")
        
        self._task_count = 0
        self._tool_calls = 0
        self._intercepted = 0
    
    def on_task_start(self, task: Any, agent: Any):
        """CrewAI task开始"""
        self._task_count += 1
        agent_role = getattr(agent, 'role', 'unknown')
        task_desc = getattr(task, 'description', 'unknown')[:80]
        self.trace.start_span("crew_task", agent=agent_role, task=task_desc)
    
    def on_task_complete(self, task: Any, output: str):
        """CrewAI task完成 → 验证输出"""
        check = self.validator.validate_output_text(output)
        if not check.valid:
            self.trace.end_span(error=f"Invalid output: {check.errors}")
            return
        self.trace.end_span(chars=len(output) if output else 0)
    
    def on_tool_use(self, tool_name: str, tool_input: Any, output: Any):
        """CrewAI工具调用 → ARK拦截"""
        self._tool_calls += 1
        
        # 幂等检查
        args_dict = {"input": str(tool_input)[:200]}
        key = self.guard.key(tool_name, args_dict)
        
        if self.guard.check(key):
            self._intercepted += 1
            return self.guard._executed[key].result
        
        # 执行追踪
        self.trace.start_span("crew_tool", tool=tool_name)
        self.trace.end_span()
    
    def on_task_error(self, error: Exception):
        """CrewAI错误"""
        if self.trace:
            self.trace.end_span(error=str(error)[:200])
    
    @property
    def report(self) -> str:
        s = self.guard.stats
        t = self.trace.summary()
        return f"""
🛡 ARK × CrewAI Trust Report
===============================
任务数: {self._task_count}
工具调用: {self._tool_calls} | 拦截重复: {self._intercepted}
幂等节约: {s['save_rate']}
链路: {t['trace_id']} | {t['total_spans']} spans
状态: {t['status']}
"""
    
    @property
    def stats(self):
        return {
            "tasks": self._task_count,
            "tool_calls": self._tool_calls,
            "intercepted": self._intercepted,
            "guard": self.guard.stats,
            "breaker": self.breaker.stats,
            "trace": self.trace.summary(),
        }
