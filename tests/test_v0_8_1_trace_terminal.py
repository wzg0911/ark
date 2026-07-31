"""
ARK v0.8.1 — Trace 终态不变式回归测试

背景：langchain-core#39163（ARK 诊断缺陷索引 F3 族第 5 例 · 新亚型「终态事件缺失」）
上游 `trace_as_chain_group` / `atrace_as_chain_group` 只 catch `Exception`，
`asyncio.CancelledError` / `KeyboardInterrupt` 绕过全部终态回调，run 永久 pending。

ARK 对该缺陷开出的处方是「终态不变式」：
    每个 started span 必须恰好到达一个终态：ok | error | cancelled | orphaned

本文件把该处方钉成 ARK 自身的回归测试 —— 我们先在自己身上强制执行。

方法论与 repro 脚本一致：**必设对照臂**。
  A/C 臂：BaseException（CancelledError / KeyboardInterrupt）
  B/D 臂：普通 Exception（控制组，证明管路本身是通的）
"""
import asyncio

import pytest
import sys

sys.path.insert(0, '/Users/w/.hermes/projects/ark/src')

from ark import Trace
from ark.trace import TERMINAL_STATES


class TestTerminalInvariantBaseException:
    """A/B/C/D 四臂对照：BaseException 不得绕过终态。"""

    def test_arm_a_async_cancelled_error_reaches_terminal(self):
        """A臂 · asyncio.CancelledError → 必须落 cancelled 终态，不得 pending"""
        t = Trace("agent")

        async def body():
            with t.start_span("llm.call"):
                raise asyncio.CancelledError("client disconnect")

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(body())

        span = t.root.children[0]
        assert span.is_terminal, "CancelledError 后 span 仍为 running → 孤儿 run"
        assert span.status == "cancelled"
        assert t.assert_terminal() == []

    def test_arm_b_control_ordinary_exception(self):
        """B臂（对照）· 普通 Exception → 终态 error，证明管路本身正常"""
        t = Trace("agent")
        with pytest.raises(ValueError):
            with t.start_span("llm.call"):
                raise ValueError("boom")

        span = t.root.children[0]
        assert span.status == "error"
        assert t.assert_terminal() == []

    def test_arm_c_keyboard_interrupt_reaches_terminal(self):
        """C臂 · KeyboardInterrupt → 必须落 cancelled 终态"""
        t = Trace("agent")
        with pytest.raises(KeyboardInterrupt):
            with t.start_span("tool.call"):
                raise KeyboardInterrupt("ctrl-c")

        span = t.root.children[0]
        assert span.status == "cancelled"
        assert t.assert_terminal() == []

    def test_arm_d_control_sync_exception(self):
        """D臂（对照）· 同步普通异常 → error"""
        t = Trace("agent")
        with pytest.raises(RuntimeError):
            with t.start_span("tool.call"):
                raise RuntimeError("bad")

        assert t.root.children[0].status == "error"
        assert t.assert_terminal() == []

    def test_system_exit_is_cancellation_not_failure(self):
        """SystemExit 同属 BaseException，归 cancelled，不污染失败率"""
        t = Trace("agent")
        with pytest.raises(SystemExit):
            with t.start_span("shutdown"):
                raise SystemExit(0)

        s = t.summary()
        assert s["cancelled"] == 1
        assert s["errors"] == 0


class TestCancelledIsSeparateTerminalState:
    """cancelled 是独立终态：留痕但不计失败率。"""

    def test_cancelled_not_counted_as_error(self):
        t = Trace("agent")
        with pytest.raises(asyncio.CancelledError):
            with t.start_span("a"):
                raise asyncio.CancelledError()

        s = t.summary()
        assert s["errors"] == 0, "取消风暴不应把失败率打爆"
        assert s["cancelled"] == 1, "但必须留痕，否则成本/延迟归因失真"
        assert s["status"] == "cancelled"

    def test_error_dominates_cancelled_in_status(self):
        t = Trace("agent")
        t.start_span("ok-one")
        t.end_span()
        with pytest.raises(asyncio.CancelledError):
            with t.start_span("cancelled-one"):
                raise asyncio.CancelledError()
        t.start_span("bad-one")
        t.end_span(error="kaboom")

        s = t.summary()
        assert s["errors"] == 1
        assert s["cancelled"] == 1
        assert s["status"] == "error"

    def test_explicit_cancelled_flag_on_end_span(self):
        t = Trace("agent")
        t.start_span("manual")
        t.end_span(cancelled=True, error="upstream cancel")

        span = t.root.children[0]
        assert span.status == "cancelled"
        assert span.error == "upstream cancel"
        assert t.summary()["errors"] == 0


class TestOrphanDetection:
    """终态存在性校验：无终态的 span 必须现形，不得静默报 ok。"""

    def test_pending_span_never_reports_ok(self):
        t = Trace("agent")
        t.start_span("leaked")
        s = t.summary()
        assert s["status"] != "ok"
        assert s["status"] == "incomplete"
        assert s["orphaned"] == 1

    def test_assert_terminal_names_the_offender(self):
        t = Trace("agent")
        t.start_span("leaked-span")
        missing = t.assert_terminal()
        assert len(missing) == 1
        assert "leaked-span" in missing[0]

    def test_close_backfills_orphaned_terminal(self):
        t = Trace("agent")
        t.start_span("outer")
        t.start_span("inner")
        assert t.close() == 2, "两个未闭合 span 都应被补发 orphaned"
        assert t.assert_terminal() == []
        for sp in (t.root.children[0], t.root.children[0].children[0]):
            assert sp.status == "orphaned"
            assert sp.end_time is not None

    def test_close_keeps_orphan_evidence_in_summary(self):
        t = Trace("agent")
        t.start_span("leaked")
        t.close()
        s = t.summary()
        assert s["orphaned"] == 1, "补发终态不等于抹掉证据"
        assert s["status"] == "incomplete"

    def test_close_on_clean_trace_is_noop(self):
        t = Trace("agent")
        t.start_span("a")
        t.end_span()
        assert t.close() == 0
        assert t.summary()["status"] == "ok"
        assert t.root.status == "ok"


class TestInvariantContract:
    """契约本身的自检。"""

    def test_terminal_states_are_exactly_four(self):
        assert set(TERMINAL_STATES) == {"ok", "error", "cancelled", "orphaned"}

    def test_every_state_renders_distinctly(self):
        t = Trace("agent")
        t.start_span("ok-one")
        t.end_span()
        t.start_span("err-one")
        t.end_span(error="e")
        t.start_span("cancel-one")
        t.end_span(cancelled=True)
        t.start_span("orphan-one")
        t.close()

        tree = t.tree()
        for icon in ("✅", "❌", "🚫", "👻"):
            assert icon in tree, f"终态 {icon} 在可视化中不可区分"

    def test_async_context_manager_also_enforces(self):
        """异步 span 上下文同样不得被 CancelledError 绕过"""
        t = Trace("agent")

        async def body():
            async with t.start_span("async.call"):
                raise asyncio.CancelledError()

        with pytest.raises(asyncio.CancelledError):
            asyncio.run(body())

        assert t.root.children[0].status == "cancelled"
        assert t.assert_terminal() == []

    def test_backward_compat_count_errors(self):
        """保留 _count_errors 旧接口语义"""
        t = Trace("agent")
        t.start_span("a")
        t.end_span(error="x")
        assert t._count_errors(t.root) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
