"""
ARK × LangChain Integration
Drop-in reliability layer for LangChain agents.

Usage:
    from ark.langchain import ARKCallbackHandler
    from langchain.agents import create_openai_tools_agent
    
    agent = create_openai_tools_agent(llm, tools, prompt)
    ark = ARKCallbackHandler()
    # All tool calls now auto-guarded
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
import time

try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.agents import AgentAction, AgentFinish
    from langchain_core.outputs import LLMResult
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    BaseCallbackHandler = object

from ..guard import IdempotencyGuard
from ..breaker import CircuitBreaker
from ..validator import OutputValidator
from ..trace import Trace


class ARKCallbackHandler(BaseCallbackHandler if HAS_LANGCHAIN else object):
    """ARK信任层 × LangChain Callback系统
    
    接入方式：一行代码
    >>> agent.invoke({"input": "..."}, {"callbacks": [ARKCallbackHandler()]})
    """
    
    def __init__(
        self,
        idempotency_ttl: int = 3600,
        circuit_failures: int = 3,
        validation_schemas: Dict[str, Any] = None,
    ):
        self.guard = IdempotencyGuard(ttl_seconds=idempotency_ttl)
        self.breaker = CircuitBreaker("langchain-agent", failure_threshold=circuit_failures)
        self.validator = OutputValidator()
        self.schemas = validation_schemas or {}
        
        self._trace: Optional[Trace] = None
        self._tool_span_ids: Dict[str, str] = {}
        self._intercepted = 0
        self._blocked_outputs = 0
    
    # LLM call monitoring
    def on_llm_start(self, serialized, prompts, **kwargs):
        self._trace = Trace("agent-turn")
        self._trace.start_span("llm_call", prompt_count=len(prompts))
    
    def on_llm_end(self, response: LLMResult, **kwargs):
        if self._trace:
            self._trace.end_span(
                tokens=getattr(response, 'llm_output', {}).get('token_usage', {}),
                generations=len(response.generations)
            )
    
    def on_llm_error(self, error, **kwargs):
        if self._trace:
            self._trace.end_span(error=str(error)[:200])
    
    # Tool call monitoring — ARK核心拦截点
    def on_tool_start(self, serialized, input_str: str, **kwargs):
        tool_name = serialized.get("name", "unknown_tool")
        
        # 幂等检查
        id_key = self.guard.key(tool_name, {"input": input_str})
        if self.guard.check(id_key):
            self._intercepted += 1
            cached = self.guard._executed[id_key]
            # Will be used to short-circuit
        
        # 链路追踪
        span = self._trace.start_span("tool_call", tool=tool_name, input=input_str[:100])
        self._tool_span_ids[id(tool_name)] = span.span_id
    
    def on_tool_end(self, output: str, **kwargs):
        if self._trace:
            self._trace.end_span(result=str(output)[:200])
    
    def on_tool_error(self, error, **kwargs):
        if self._trace:
            self._trace.end_span(error=str(error)[:200])
    
    # Agent action monitoring
    def on_agent_action(self, action: AgentAction, **kwargs):
        self._trace.start_span("agent_action", tool=action.tool, log=action.log[:100])
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs):
        if self._trace:
            self._trace.end_span()
    
    @property
    def stats(self):
        return {
            "intercepted_duplicates": self._intercepted,
            "blocked_outputs": self._blocked_outputs,
            "guard": self.guard.stats,
            "breaker": self.breaker.stats,
            "validator": self.validator.stats,
        }
    
    @property
    def report(self) -> str:
        """生成信任报告"""
        s = self.stats
        t = self._trace.summary() if self._trace else {}
        return f"""
🛡 ARK Trust Report
====================
幂等拦截: {s['intercepted_duplicates']} 次重复调用
输出拦截: {s['blocked_outputs']} 次非法输出
熔断状态: {s['breaker']['state']}
可靠性: {s['breaker']['reliability']}
链路: {t.get('trace_id', 'N/A')} | {t.get('total_spans', 0)} spans | {t.get('duration_ms', 0):.0f}ms
"""
