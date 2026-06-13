"""
F9 Error Compressor Tests — Day 1 重构
覆盖 12-Factor Agents Factor 9（错误压缩）
"""

import time
import pytest
from ark.errors import (
    truncate_error,
    error_to_llm_context,
    should_retry,
    retry_delay,
    ErrorContext,
    error_context,
    with_retry,
    NON_RETRYABLE_TYPES,
)


# ━━━━━━━━━━ 1. truncate_error ━━━━━━━━━━

class TestTruncateError:
    def test_basic_truncation(self):
        try:
            raise ValueError("hello world")
        except ValueError as e:
            err = truncate_error(e)
        
        assert err["type"] == "ValueError"
        assert err["message"] == "hello world"
        assert err["raw_hash"] is not None
        assert len(err["raw_hash"]) == 8
    
    def test_long_message_truncated(self):
        long_msg = "x" * 1000
        try:
            raise RuntimeError(long_msg)
        except RuntimeError as e:
            err = truncate_error(e, max_message_length=100)
        
        assert len(err["message"]) <= 103  # 100 + "..."
        assert err["message"].endswith("...")
    
    def test_stack_tail_preserved(self):
        try:
            def deep():
                raise KeyError("nested")
            def mid():
                deep()
            def outer():
                mid()
            outer()
        except KeyError as e:
            err = truncate_error(e, max_stack_lines=3)
        
        assert err["type"] == "KeyError"
        # 末 3 行非空
        non_empty = [line for line in err["stack_tail"] if line.strip()]
        assert len(non_empty) >= 1


# ━━━━━━━━━━ 2. error_to_llm_context ━━━━━━━━━━

class TestErrorToLLMContext:
    def test_first_attempt_no_hint(self):
        try:
            raise ValueError("bad input")
        except ValueError as e:
            ctx = error_to_llm_context(e, "test_tool", attempt=1)
        
        assert "[ERROR]" in ctx
        assert "test_tool" in ctx
        assert "attempt 1" in ctx
        assert "ValueError" in ctx
        assert "Hint:" not in ctx  # 第一次失败不给提示
    
    def test_repeat_attempt_gives_hint(self):
        try:
            raise ConnectionError("timeout")
        except ConnectionError as e:
            ctx = error_to_llm_context(e, "fetch_data", attempt=2)
        
        assert "Hint:" in ctx
        assert "Different" in ctx  # 引导换思路
    
    def test_third_attempt_suggests_escalation(self):
        try:
            raise RuntimeError("boom")
        except RuntimeError as e:
            ctx = error_to_llm_context(e, "flaky_tool", attempt=3)
        
        assert "Escalate" in ctx
    
    def test_previous_attempts_shown(self):
        try:
            raise ValueError("v1")
        except ValueError as e:
            ctx = error_to_llm_context(
                e, "tool", attempt=3,
                previous_attempts=[
                    {"type": "ValueError", "message": "v1"},
                    {"type": "ValueError", "message": "v2"},
                ]
            )
        
        assert "Previous attempts" in ctx
        assert "v1" in ctx or "v2" in ctx


# ━━━━━━━━━━ 3. should_retry ━━━━━━━━━━

class TestShouldRetry:
    def test_below_limit_can_retry(self):
        assert should_retry(ValueError("x"), attempt=1, max_attempts=3) is True
        assert should_retry(ValueError("x"), attempt=2, max_attempts=3) is True
    
    def test_at_limit_cannot_retry(self):
        assert should_retry(ValueError("x"), attempt=3, max_attempts=3) is False
        assert should_retry(ValueError("x"), attempt=5, max_attempts=3) is False
    
    def test_non_retryable_types(self):
        for exc_type in NON_RETRYABLE_TYPES:
            cls = type(exc_type, (Exception,), {})
            exc = cls("test")
            assert should_retry(exc, attempt=1, max_attempts=5) is False, \
                f"{exc_type} should not be retryable"


# ━━━━━━━━━━ 4. retry_delay 指数退避 ━━━━━━━━━━

class TestRetryDelay:
    def test_exponential_growth(self):
        d1 = retry_delay(1, base_delay=1.0, backoff_factor=2.0)
        d2 = retry_delay(2, base_delay=1.0, backoff_factor=2.0)
        d3 = retry_delay(3, base_delay=1.0, backoff_factor=2.0)
        assert d1 == 1.0
        assert d2 == 2.0
        assert d3 == 4.0
    
    def test_capped_at_max(self):
        d10 = retry_delay(10, base_delay=1.0, max_delay=30.0, backoff_factor=2.0)
        assert d10 == 30.0


# ━━━━━━━━━━ 5. ErrorContext 累加器 ━━━━━━━━━━

class TestErrorContext:
    def test_record_and_count(self):
        ctx = ErrorContext(tool_name="send_email")
        try:
            raise ValueError("v1")
        except ValueError as e:
            ctx.record_failure(e, attempt=1)
        
        assert ctx.failure_count == 1
        assert ctx.last_error is not None
    
    def test_escalation_after_max_attempts(self):
        ctx = ErrorContext(tool_name="api_call", max_attempts=3)
        for i in range(1, 4):
            try:
                raise ConnectionError(f"fail {i}")
            except ConnectionError as e:
                ctx.record_failure(e, attempt=i)
        
        assert ctx.should_escalate is True
    
    def test_immediate_escalation_for_non_retryable(self):
        ctx = ErrorContext(tool_name="auth_call", max_attempts=3)
        try:
            raise PermissionError("denied")
        except PermissionError as e:
            ctx.record_failure(e, attempt=1)
        
        assert ctx.should_escalate is True  # 不可重试 → 立即升级
    
    def test_to_llm_context_renders(self):
        ctx = ErrorContext(tool_name="t", max_attempts=3)
        try:
            raise ValueError("x")
        except ValueError as e:
            ctx.record_failure(e, attempt=1)
        
        text = ctx.to_llm_context()
        assert "t" in text
        # 末 1 行不影响 — 只验证上下文含记录
        assert "attempt 1" in text
        assert "ValueError" in text or "x" in text
    
    def test_to_dict_serializable(self):
        ctx = ErrorContext(tool_name="t", max_attempts=3)
        try:
            raise ValueError("x")
        except ValueError as e:
            ctx.record_failure(e, attempt=1)
        
        d = ctx.to_dict()
        assert d["tool_name"] == "t"
        assert d["failure_count"] == 1
        assert isinstance(d["records"], list)


# ━━━━━━━━━━ 6. with_retry 装饰器 ━━━━━━━━━━

class TestWithRetryDecorator:
    def test_success_no_retry(self):
        call_count = {"n": 0}
        
        @with_retry(tool_name="ok", max_attempts=3)
        def func():
            call_count["n"] += 1
            return "success"
        
        assert func() == "success"
        assert call_count["n"] == 1
    
    def test_retry_then_succeed(self):
        call_count = {"n": 0}
        
        @with_retry(tool_name="flaky", max_attempts=3)
        def func():
            call_count["n"] += 1
            if call_count["n"] < 2:
                raise ConnectionError("transient")
            return "ok"
        
        # base_delay=1 → 第一次失败后等 1s
        result = func()
        assert result == "ok"
        assert call_count["n"] == 2
    
    def test_give_up_after_max(self):
        @with_retry(tool_name="broken", max_attempts=2)
        def func():
            raise ValueError("always fails")
        
        with pytest.raises(RuntimeError) as exc_info:
            func()
        assert "All 2 attempts failed" in str(exc_info.value)
    
    def test_fallback_used_on_failure(self):
        @with_retry(tool_name="primary", max_attempts=2, fallback=lambda: "fallback_value")
        def func():
            raise ValueError("fail")
        
        # Note: base_delay=1s × 1 = 1s total wait
        assert func() == "fallback_value"
    
    def test_non_retryable_immediate_fallback(self):
        @with_retry(tool_name="auth", max_attempts=5, fallback=lambda: "unauthorized_default")
        def func():
            raise PermissionError("denied")
        
        # 不可重试 → 立即走 fallback
        assert func() == "unauthorized_default"
    
    def test_error_context_exposed(self):
        @with_retry(tool_name="t", max_attempts=3)
        def func():
            return 1
        
        assert hasattr(func, "error_context")
        assert func.error_context.tool_name == "t"


# ━━━━━━━━━━ 7. error_context 上下文管理器 ━━━━━━━━━━

class TestErrorContextManager:
    def test_no_error_no_records(self):
        with error_context("safe_tool") as ctx:
            _ = 1 + 1
        assert ctx.failure_count == 0
    
    def test_exception_caught_records(self):
        # error_context 设计为吞咽 + 记录（不重抛）
        with error_context("danger_tool", max_attempts=3) as ctx:
            raise ValueError("boom")
        
        # ctx 记录了错误（1 次）
        assert ctx.failure_count == 1
        # ValueError 可重试且未达上限 → 不升级
        assert ctx.should_escalate is False
        assert ctx.last_error["retryable"] is True


# ━━━━━━━━━━ 8. 集成测试：F9 + F3 + F5 ━━━━━━━━━━

class TestF9Integration:
    def test_retry_history_feeds_llm_context(self):
        """
        完整流程：
        1. 工具失败 3 次
        2. ErrorContext 记录全部
        3. 升级判断 should_escalate = True
        4. 喂给 LLM 的 context 包含全部历史
        """
        ctx = ErrorContext(tool_name="flaky_api", max_attempts=3)
        
        for attempt in range(1, 4):
            try:
                raise ConnectionError(f"timeout #{attempt}")
            except ConnectionError as e:
                ctx.record_failure(e, attempt=attempt)
        
        # F5: 完整状态可序列化
        state = ctx.to_dict()
        assert state["failure_count"] == 3
        
        # F9: 升级判断
        assert ctx.should_escalate is True
        
        # F3 + F9: 喂给 LLM 的 context
        llm_text = ctx.to_llm_context()
        assert "ESCALATE" in llm_text
        assert "ConnectionError" in llm_text
        assert "attempt 3" in llm_text or "attempt" in llm_text
    
    def test_full_12factor_recipe(self):
        """
        完整 12-Factor F9 自检：截断 + 重试上限 + 升级路径
        """
        # ✅ 截断：错误信息不会撑爆 context
        try:
            raise ValueError("x" * 10000)
        except ValueError as e:
            err = truncate_error(e, max_message_length=200)
            assert len(err["message"]) < 250  # 截断生效
        
        # ✅ 重试上限
        assert should_retry(ValueError("x"), attempt=3, max_attempts=3) is False
        
        # ✅ 升级路径
        ctx = ErrorContext(tool_name="t", max_attempts=3)
        for i in range(1, 4):
            try:
                raise ValueError(f"f{i}")
            except ValueError as e:
                ctx.record_failure(e, attempt=i)
        assert ctx.should_escalate is True
        # 原异常类型保留
        assert ctx.last_error["type"] == "ValueError"
