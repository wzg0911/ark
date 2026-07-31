# ARK repro: langchain#39163 — `trace_as_chain_group` / `atrace_as_chain_group`
# leave the started run PENDING when the body raises a non-`Exception`
# `BaseException` (asyncio.CancelledError / KeyboardInterrupt).
#
# F3 family (silent failure / terminal-callback never fires), 5th occurrence —
# but a NEW sub-shape: not "failure disguised as success", but
# "failure disguised as NOTHING" (no terminal event at all → run stays open).
#
# Root cause (offline-verifiable): both context managers in
# `langchain_core.callbacks.manager` wrap the body in `except Exception as e:`,
# although the underlying group managers accept `BaseException` and the
# runnable callback helpers in the SAME module already catch `BaseException`.
# `asyncio.CancelledError` and `KeyboardInterrupt` inherit directly from
# `BaseException`, so they bypass BOTH `on_chain_error()` and `on_chain_end()`.
#
# Real-world trigger: ASGI / WebSocket apps — a client disconnect cancels the
# request task, which silently orphans the trace in LangSmith.
#
# Deterministic OFFLINE verification (no API key, no network): we install a
# recording AsyncCallbackHandler / CallbackHandler and count terminal events.
#
# Usage:
#   python -m venv venv && venv/bin/pip install langchain-core
#   venv/bin/python repro_39163_cancelled_leaves_run_pending.py
import asyncio
from typing import Any
from unittest.mock import patch
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler, BaseCallbackHandler
from langchain_core.callbacks.manager import (
    AsyncCallbackManager,
    CallbackManager,
    atrace_as_chain_group,
    trace_as_chain_group,
)

SEP = "=" * 78


class AsyncRecorder(AsyncCallbackHandler):
    def __init__(self) -> None:
        self.started = 0
        self.ended = 0
        self.errors: list[BaseException] = []

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.started += 1

    async def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.ended += 1

    async def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.errors.append(error)


class SyncRecorder(BaseCallbackHandler):
    def __init__(self) -> None:
        self.started = 0
        self.ended = 0
        self.errors: list[BaseException] = []

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.started += 1

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.ended += 1

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self.errors.append(error)


def _fmt(rec: Any) -> str:
    return f"started={rec.started} ended={rec.ended} errors={len(rec.errors)}"


# --------------------------------------------------------------------------
# Case A (async) — asyncio.CancelledError inside atrace_as_chain_group
# --------------------------------------------------------------------------
async def case_a_async_cancelled() -> AsyncRecorder:
    rec = AsyncRecorder()
    manager = AsyncCallbackManager(handlers=[rec])
    with patch(
        "langchain_core.tracers.context._get_trace_callbacks",
        return_value=manager,
    ):
        try:
            async with atrace_as_chain_group("cancelled"):
                raise asyncio.CancelledError("cancelled")
        except asyncio.CancelledError:
            pass
    return rec


# --------------------------------------------------------------------------
# Case B (async CONTROL) — ordinary Exception inside atrace_as_chain_group
#   proves the plumbing works; only BaseException escapes it
# --------------------------------------------------------------------------
async def case_b_async_exception() -> AsyncRecorder:
    rec = AsyncRecorder()
    manager = AsyncCallbackManager(handlers=[rec])
    with patch(
        "langchain_core.tracers.context._get_trace_callbacks",
        return_value=manager,
    ):
        try:
            async with atrace_as_chain_group("boom"):
                raise ValueError("boom")
        except ValueError:
            pass
    return rec


# --------------------------------------------------------------------------
# Case C (sync) — KeyboardInterrupt inside trace_as_chain_group
# --------------------------------------------------------------------------
def case_c_sync_keyboardinterrupt() -> SyncRecorder:
    rec = SyncRecorder()
    manager = CallbackManager(handlers=[rec])
    with patch(
        "langchain_core.tracers.context._get_trace_callbacks",
        return_value=manager,
    ):
        try:
            with trace_as_chain_group("interrupted"):
                raise KeyboardInterrupt("interrupted")
        except KeyboardInterrupt:
            pass
    return rec


# --------------------------------------------------------------------------
# Case D (sync CONTROL) — ordinary Exception inside trace_as_chain_group
# --------------------------------------------------------------------------
def case_d_sync_exception() -> SyncRecorder:
    rec = SyncRecorder()
    manager = CallbackManager(handlers=[rec])
    with patch(
        "langchain_core.tracers.context._get_trace_callbacks",
        return_value=manager,
    ):
        try:
            with trace_as_chain_group("boom"):
                raise ValueError("boom")
        except ValueError:
            pass
    return rec


def main() -> None:
    import langchain_core

    print(SEP)
    print("ARK repro · langchain#39163")
    print("trace_as_chain_group leaves runs pending on BaseException")
    print(f"langchain_core == {langchain_core.__version__}")
    print(SEP)

    a = asyncio.run(case_a_async_cancelled())
    b = asyncio.run(case_b_async_exception())
    c = case_c_sync_keyboardinterrupt()
    d = case_d_sync_exception()

    rows = [
        ("A", "async  · asyncio.CancelledError", a, False),
        ("B", "async  · ValueError    (control)", b, True),
        ("C", "sync   · KeyboardInterrupt      ", c, False),
        ("D", "sync   · ValueError    (control)", d, True),
    ]

    print(f"{'#':<3}{'case':<34}{'counts':<40}{'verdict'}")
    print("-" * 78)
    bug_confirmed = True
    control_ok = True
    for tag, name, rec, expect_terminal in rows:
        terminal = rec.ended + len(rec.errors)
        ok = (terminal > 0) == expect_terminal
        if expect_terminal:
            control_ok = control_ok and ok
            verdict = "OK (terminal fired)" if ok else "UNEXPECTED"
        else:
            bug_confirmed = bug_confirmed and (terminal == 0)
            verdict = "BUG: run left PENDING" if terminal == 0 else "not reproduced"
        print(f"{tag:<3}{name:<34}{_fmt(rec):<40}{verdict}")

    print(SEP)
    print("Invariant that ARK OutputValidator/Trace enforces:")
    print("  every started span MUST reach exactly one terminal state")
    print("  (end | error) — regardless of BaseException class.")
    print(SEP)
    if bug_confirmed and control_ok:
        print("RESULT: 4/4 as predicted — #39163 REPRODUCED offline.")
        print("  A & C: started=1, ended=0, errors=0  -> orphaned run")
        print("  B & D: terminal callback fires normally -> plumbing is fine")
    else:
        print("RESULT: NOT fully reproduced on this version.")


if __name__ == "__main__":
    main()
