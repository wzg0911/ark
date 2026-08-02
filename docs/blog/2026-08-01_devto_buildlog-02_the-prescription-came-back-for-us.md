---
title: "The Prescription Came Back For Us: Three Times We Diagnosed a Framework Bug and Found the Same Bug in Our Own Code"
published: false
description: "Build log #2 — we autopsy a LangChain cancellation bug that leaves traces open forever. Then we run the same prescription on ARK itself. It hit. So we did it twice more. Here's the uncomfortable method that keeps working."
tags: ai, python, opensource, reliability
canonical_url: https://github.com/wzg0911/ark
series: ARK Build Log
---

> **Build Log #2** · 2026-08-01 · [ARK — Agent Reliability Kit](https://github.com/wzg0911/ark)
>
> Entry two of a public build log. No launch, no roadmap fantasy — just what we shipped and what the evidence forced us to admit about our own code.

---

## The one-paragraph version

In [Build Log #1](https://github.com/wzg0911/ark) we promised a full autopsy of `langchain-core#39163` — a bug where a cancelled agent run leaves its trace open forever, reported as healthy. We did the autopsy. Then we did something we didn't plan: we took the *prescription* we wrote for LangChain and ran it against ARK's own tracer. It hit. Our tracer had the exact same defect — an unclosed span was being summarized as `ok`, and worse, a test was pinning that wrong behavior as if it were correct.

So we fixed ours. Then, over the next two upstream diagnoses, we did the same self-audit — and it hit both times. Three consecutive upstream reports, three same-shape defects found in our own code. This post is about that loop, because the loop turned out to be the actual product.

---

## Part 1 — The autopsy: `#39163`, failure disguised as *nothing*

Most silent failures we've catalogued are "failure disguised as success" — a function returns a healthy-looking result that is wrong. `#39163` is a rarer, nastier sub-shape: **failure disguised as nothing at all.**

`trace_as_chain_group` and `atrace_as_chain_group` in `langchain_core.callbacks.manager` wrap their body like this:

```python
try:
    yield run_manager
except Exception as e:        # <-- Exception, not BaseException
    run_manager.on_chain_error(e)
    raise
else:
    run_manager.on_chain_end({})
```

`asyncio.CancelledError` and `KeyboardInterrupt` inherit directly from `BaseException`, **not** from `Exception`. So when a body is cancelled, it bypasses *both* branches. `on_chain_error()` never fires. `on_chain_end()` never fires. The run that was started is never terminated — it just stays open.

The real-world trigger isn't exotic. Any ASGI/WebSocket agent app: a client disconnects, the request task is cancelled, and the trace in your observability backend is silently orphaned. You don't get an error. You get a run that is permanently, quietly, pending. Your dashboards look clean. The incident is invisible by construction.

The tell is that the *same module* already knows better — the runnable callback helpers a few hundred lines down catch `BaseException`. The context managers just didn't get the memo. It's not a hard bug. It's a two-word fix (`Exception` → `BaseException`). But you cannot see it from a type checker, a schema validator, or an APM trace, because nothing ever went wrong on the wire. The absence of a terminal event is not an event.

**How we verified it offline.** No API key, no network. We install a recording `AsyncCallbackHandler`, run the group body, cancel it, and count terminal callbacks:

- Arm A (`CancelledError`): terminal events fired = **0**. Run left pending.
- Arm B (control, `ValueError`): `on_chain_error` fired = **1**. Pipeline proven healthy.

Half of a reproduction is the control arm. Without Arm B, "it didn't fire" just means your harness is broken. The repro is standalone: [`scripts/repros/repro_39163_cancelled_leaves_run_pending.py`](https://github.com/wzg0911/ark/tree/main/scripts/repros).

**The prescription — written as an invariant, not advice.** "Be careful with cancellation" is advice. The invariant is:

> Every started span must reach exactly one terminal state. The terminal set is `{ok, error, cancelled, orphaned}` — and *cancelled is a legitimate terminal state, not a failure.*

That last clause is the part that's harder than it looks. If you naively treat cancellation as an error, a client-disconnect storm trips your circuit breaker and takes down a healthy service. Cancellation must be *counted and closed*, but must not inflate your error rate. Four states, not two.

---

## Part 2 — The prescription came back for us

Here's the part we didn't plan.

Having written "every started span must reach exactly one terminal state" for LangChain, the obvious question was: **does ARK's own `Trace` satisfy the invariant it just prescribed?**

It did not. Three gaps, self-inflicted:

1. `summary()` returned `status=ok` for any span that had a start and no end. An orphan was being laundered into a healthy result — *the identical defect we'd just diagnosed in `#39163`.*
2. `cancelled` was lumped in with ordinary exceptions and counted toward `errors`. A disconnect storm would blow up our own failure rate — the exact anti-pattern the invariant warned about.
3. There was no terminal-state existence check at all.

And the worst detail, the one that stung: a test — `test_f9_trace_no_end` — was **asserting that the unclosed-span-reports-`ok` behavior was correct.** We had pinned our own bug as a contract. The autopsy didn't just find a bug in our code; it found a bug we had actively protected with a green test.

The fix (v0.8.1) established the four-state terminal set for real:

- `TERMINAL_STATES = {ok, error, cancelled, orphaned}`
- `Span.__exit__` handles `BaseException`; `CancelledError`/`KeyboardInterrupt`/`SystemExit` map to `cancelled`, not `error`
- `Trace.assert_terminal()` enumerates any span that never terminated
- `Trace.close()` stamps unclosed spans as `orphaned` and *keeps the evidence* instead of silently finalizing
- status priority `error > incomplete > cancelled > ok`
- the wrong test assertion was corrected: `ok` → `incomplete`

Regression: 248 → 265 passed / 3 skipped, green.

---

## Part 3 — So we did it two more times

Once is an anecdote. We wanted to know if the loop was real, so we kept running the self-audit on the next two upstream diagnoses.

### Reflow #2 — `langchain-core#39152` → ARK `OutputValidator` (v0.8.2)

The upstream bug: `DictPromptTemplate.format()` silently **deletes** any list/tuple item that isn't a `str` or `dict`. The root cause isn't a missing `else` — it's *two contradictory null policies four lines apart in one function*:

```python
elif isinstance(v, (list, tuple)):
    formatted_v = []
    for x in v:
        if isinstance(x, str):    formatted_v.append(formatter(x, **inputs))
        elif isinstance(x, dict): formatted_v.append(_insert_input_variables(x, ...))
    formatted[k] = type(v)(formatted_v)   # <-- no else: item vanishes
else:
    formatted[k] = v                       # <-- scalar OUTSIDE a list survives
```

The same `1` is preserved at `{"scalar": 1}` and destroyed at `{"nums": [1]}`. Loss depends only on the *container the value sits in*. Numeric fields in multimodal content blocks — `bbox`, `dims`, `amount_cents`, score arrays — are exactly what disappears.

The self-audit hit: ARK's `OutputValidator.validate()` was filtering out schema-undeclared fields and still returning `valid=True, errors=[]`. In a payment payload, `currency`, `idempotency_key`, and `line_items` evaporated with **zero signal** to the caller. Same shape as `#39152`: silent structural loss reported as success.

The fix established a structure-conservation invariant — `dropped_fields`, `lossless`, `strict_extra`, and an `ark.validation.dropped` event so a dropped field can never again be silent. 281 passed / 3 skipped, green.

### Reflow #3 — `langchain-exa#39167` → ARK attribute access (v0.8.3)

The upstream bug is two defects pointing in opposite directions inside one seven-line function:

```python
if getattr(result, "highlights"):   # <-- TWO-ARG getattr
    metadata["highlights"] = result.highlights
```

**Defect 1 — the guard that isn't.** `getattr(x, "y")` with no default is *exactly* `x.y`. It raises on a missing attribute. The code *reads* as defensive — `getattr` is the universal idiom for "tolerate absence" — but the missing third argument means it behaves like a plain attribute access. The defense is decorative.

**Defect 2 — truthiness used as presence.** Even when the attribute exists, `if <value>:` drops `[]`, `""`, `0.0`. "Searched, found no highlights" (`highlights=[]`) and "highlights never requested" collapse into the same output. Meanwhile the dict literal six lines up keeps `title=None` and `score=0.0` unconditionally. Two opposite null policies in one function.

The self-audit hit ARK's `langchain.py::on_llm_end`: `getattr(response, 'llm_output', {}).get(...)`. `llm_output` is declared `dict | None`, defaulting to `None`. Absence was guarded; `None` was not — so the guard *never fired*, and `.get()` on `None` detonated one frame later. Same shape: absence handled, falsy/None not.

The fix (`src/ark/attrs.py`: `attr` / `attr_mapping` / `attr_text` / `is_present` / `prune_absent`) established the invariant:

> Optional attribute reads must be *total functions*: absence or `None` both map to a sentinel, and a falsy-but-present value is never mistaken for absence.

We also caught two collateral bugs while there — a present-but-`None` `description` slicing into a `TypeError` in the CrewAI callback, and out-of-package relative imports (`..guard` → `.guard`). 300 passed / 3 skipped, green.

---

## What the loop actually means

Three upstream reports. Three same-shape defects in our own code. That is not us being sloppy — or rather, it *is*, but it's the specific kind of sloppy that every codebase shares, because these defects are not typos. They are **contracts that exist only as convention:**

- "a started run must terminate" — assumed, never enforced
- "format is pass-through" — documented, silently false for one container type
- "this `getattr` tolerates absence" — reads true, behaves false

None of them are catchable by the tools we already trust. The type checker is happy — `None` is a valid `dict | None`. Schema validation is happy — a dropped field was never in the schema. APM is happy — nothing errored on the wire. The value is often perfectly well-typed and perfectly wrong.

The only thing that catches a convention-only contract is turning it into a **runtime invariant with a single enforcement checkpoint.** That's the entire thesis of ARK, and the reflow loop is the cheapest possible test of it: if writing an invariant for someone else's bug immediately exposes the same bug in your own code, the invariant was worth writing.

We're not going to pretend this makes ARK bug-free. It makes ARK *honest about a class of bug it can now see.* Different claim.

---

## The method, still boring, still working

1. Diagnose a real upstream issue → write the prescription as an **invariant**, not advice.
2. Before shipping the report, run that invariant against your own code. Assume you have the bug.
3. When you find it (you will), fix it *and* add the regression — and check whether an existing test was pinning the wrong behavior.
4. Count states, don't collapse them. `cancelled` is not `error`. Absent is not empty. Well-typed is not correct.
5. Keep the evidence. An orphaned span stamped `orphaned` beats a silent finalize every time.

All repros are standalone in [`scripts/repros/`](https://github.com/wzg0911/ark/tree/main/scripts/repros) — clone and run, no keys.

---

## What's next

- Build log #3: what happens when the same defect family shows up in *three different frameworks* — and whether "one enforcement point" survives contact with three different call conventions.
- Weekly diagnostic digests as they're written.
- Diagnostic pipeline automation: self-serve upload → automated analysis → public report.

If you maintain an agent framework or adapter and want an outside autopsy on a specific issue, the pipeline is free and the reports are public. Open an issue on the repo.

---

**ARK — Agent Reliability Kit.** MIT licensed. Trust infrastructure for AI agents.

[GitHub](https://github.com/wzg0911/ark) · [PyPI `ark-trust`](https://pypi.org/project/ark-trust/) · [npm `@feilunxitong/arkit`](https://www.npmjs.com/package/@feilunxitong/arkit) · Go: `go get github.com/wzg0911/ark-go`

*Defect pattern index (23 reports / 10 families): [`docs/reports/ark-defect-pattern-index.md`](https://github.com/wzg0911/ark/blob/main/docs/reports/ark-defect-pattern-index.md)*
