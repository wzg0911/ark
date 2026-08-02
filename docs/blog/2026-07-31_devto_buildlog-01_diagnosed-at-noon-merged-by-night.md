---
title: "Diagnosed at Noon, Merged by Night: What 21 LangChain Bug Autopsies Taught Us About Agent Reliability"
published: false
description: "Build log #1 — we run a diagnostic pipeline over real LangChain/LangGraph issues. One report was merged upstream the same day. Here's the method, the receipts, and the uncomfortable pattern underneath."
tags: ai, python, opensource, reliability
canonical_url: https://github.com/wzg0911/ark
series: ARK Build Log
---

> **Build Log #1** · 2026-07-31 · [ARK — Agent Reliability Kit](https://github.com/wzg0911/ark)
>
> This is the first entry in a public build log. No launch announcement, no roadmap fantasy — just what we actually shipped and what the evidence forced us to change our minds about.

---

## The one-paragraph version

We built a diagnostic pipeline that takes a real open issue from a major agent framework, reproduces it deterministically in an isolated environment (pinned versions, no network, no API keys where possible), traces it to a root cause, and writes a prescription. We've done this 21 times over four weeks against LangChain, LangChain-core, and provider adapters.

On 2026-07-28, one of those reports (`langchain-anthropic#39100`) was published in the morning. By that evening a maintainer had merged [PR #39101](https://github.com/langchain-ai/langchain/pull/39101) — and the fix was the same fix our report prescribed: an outbound field-sanitization pass on the system-message branch.

We did not open that PR. We did not comment on the issue. The value was in being right, on the record, on the same day.

---

## Why we do autopsies instead of feature work

The honest origin story: we were building reliability primitives (idempotency guard, circuit breaker, output validator, trace) and kept getting the same question — *"is this a real problem or are you inventing one?"*

Fair question. The only non-hand-wavy answer is receipts. So instead of writing more marketing copy about hypothetical duplicate payments, we started dissecting failures that already exist, in public, in the most popular agent framework on earth.

Four weeks in, 21 reports collapse into **9 recurring defect families**. That collapse is the actual finding. These aren't 21 unrelated bugs — they're 9 structural seams that keep re-opening.

---

## The three findings that changed how we think

### 1. Point fixes cannot outrun an N×M contract surface

LangChain v1's content-block API mints an internal `lc_<uuid4>` id on every block. Every provider adapter must strip that id before it goes on the wire. Miss one branch, get a `400`.

Here's the state of two adapters when we looked:

| | human | system | assistant |
|---|---|---|---|
| **Anthropic** | ✅ stripped | ❌ **leaked** (#39100) | ✅ stripped |
| **OpenAI** | ✅ stripped | ✅ stripped | ❌ **leaked** (#39113) |

Two adapters, each getting two-thirds right, each missing a *different* branch. Perfectly complementary holes.

The sharp part isn't the symmetry. It's what happened next: the merged fix for #39100 patched **Anthropic/system only**. The OpenAI/assistant twin survived the same-day fix and was independently reported by someone else on that same day.

That's the whole argument for a trust layer in one data point. The failure probability scales with `adapters × role branches`, and every cell depends on a human remembering an implicit convention. You cannot patch your way out of a combinatorial surface — you can only move the enforcement to a single outbound contract checkpoint.

### 2. There is a class of bug that produces no wrong value at all

Most "silent failure" bugs still emit *something* wrong — a bad field, a fabricated success message. You can audit for it after the fact because a contradiction exists in the data.

`langchain-core#39163` removes even that.

`trace_as_chain_group` / `atrace_as_chain_group` wrap cleanup in `except Exception`. But `asyncio.CancelledError` and `KeyboardInterrupt` inherit from `BaseException` — they slip past. The run gets a start event, and then: no end, no error. Forever pending.

Our offline reproduction (langchain-core 1.5.3, no API key, no network):

```
A  async · asyncio.CancelledError   started=1 ended=0 errors=0   BUG: run left PENDING
B  async · ValueError    (control)  started=1 ended=0 errors=1   OK  (terminal fired)
C  sync  · KeyboardInterrupt        started=1 ended=0 errors=0   BUG: run left PENDING
D  sync  · ValueError    (control)  started=1 ended=0 errors=1   OK  (terminal fired)
```

B and D are the control arms — they prove the callback pipeline itself is fine. The defect localizes to one word: the exception base class in a `catch` clause.

Three things make this the most instructive bug in our index:

- **The trigger is production-normal, not edge-case.** Any ASGI/WebSocket client disconnect raises `CancelledError`. The more interactive your service, the more polluted your telemetry — an inverse relationship where the systems you most need to observe are the ones you can least trust.
- **The correct pattern already exists in the same file.** Runnable callback helpers in `manager.py` catch `BaseException`. The two chain-group context managers don't. This isn't a design tradeoff; it's discipline drift — direct physical evidence that "just remember to do it right" doesn't hold at scale.
- **It happened inside the observability component.** The module whose entire job is recording what happened lacks a terminal-state invariant for itself.

An orphaned span is, in every telemetry backend we know of, **indistinguishable from a genuinely long-running task**. Your p99 is wrong and nothing will ever tell you.

### 3. Some bugs never throw, never return anything invalid, and are exactly backwards

`langchain-qdrant#39052`: two layers each apply a mirror convention to `lambda_mult`. Composed, they cancel — and MMR search semantics invert. Ask for maximum diversity, get maximum similarity. No exception. No invalid value. Type checker happy. Schema validation happy. Result precisely opposite to intent.

`langchain-core#39047`: a deprecation warning nudges you off `key_encoder="sha1"`. But only the sha1 branch wraps its digest in `uuid.uuid5()`. Follow the official advice, and any UUID-validating vectorstore rejects every write — 4/4 in our matrix. On stores that *don't* validate, it's worse: every document silently changes identity, incremental indexing loses its dedup anchors, and you get phantom rewrites instead of an error.

A crash you see is a bug. A crash you don't see is a data-loss incident.

---

## What we got wrong (the honest section)

Two of our reports this week — the F7 "non-deterministic consistency" family — did **not** fully reproduce.

`#39087` claims `InMemoryRecordManager.update()` calls `get_time()` per document, causing intra-batch timestamp drift that makes `cleanup="full"` silently under-delete. We confirmed the anti-pattern at source level (the drift is real, ~0.1ms within a batch). But the actual `num_deleted` discrepancy **did not trigger in 5/5 local attempts**.

We're not writing that up as "reproduced." And we're not going to run it 500 times until we get a hit, because *that's the point*: when the trigger is non-deterministic, "just test more" is not a strategy. The only thing that makes an intermittent invariant violation visible on the run where it actually happens is a runtime invariant check (`expected_deleted == actual_deleted`) plus a trace record.

The failure to reproduce is itself the argument.

Worth noting the mirror structure: `#39087` is a clock that's too *fast* (intra-batch drift crosses the cutoff); `#39106` is a clock that's too *slow* (insufficient resolution causes equal-timestamp collisions with a `>=` boundary). Same cleanup predicate, opposite clock pathologies. And `SQLRecordManager` uses strict `<` where `InMemoryRecordManager` uses `>=` — two implementations of one abstraction with inconsistent boundary semantics.

---

## The method, in case you want to steal it

Nothing here is clever. It's just disciplined.

1. **Pick a real open issue.** Not a synthesized example. Public, dated, verifiable.
2. **Reproduce offline and deterministically.** Isolated venv, pinned versions, no network, no API keys. If a provider call is involved, inspect the *outbound payload* rather than hitting the endpoint — you almost always can.
3. **Always run a control arm.** Our `CancelledError` repro is worthless without the `ValueError` arm proving the pipeline works. Half of "reproduction" is ruling out your own environment.
4. **Trace to a specific line or contract**, not a subsystem. "The callback system is fragile" is not a root cause. "This `except Exception` should be `except BaseException`" is.
5. **Write the prescription as a runtime invariant**, not advice. "Be careful to strip ids" is advice. "Outbound payload must match provider wire-schema allowlist, enforced at one checkpoint" is an invariant.
6. **Publish what didn't reproduce.** See above.

All 6 repro scripts live in [`scripts/repros/`](https://github.com/wzg0911/ark/tree/main/scripts/repros). They're standalone — clone and run.

---

## Where ARK actually sits

The defect families map to enforcement points, not features:

| Defect family | Seen in | Enforcement point |
|---|---|---|
| Duplicate execution | #34974, #38708 | Idempotency key computed from normalized args, checked pre-execution |
| Per-call config mutating instance state | #38779, #38840, #38989 | Immutable input contract + per-call isolation |
| Silent failure / success-shaped failure | #39039, #38892, #38893, #39099, #39163 | Output validation + terminal-state existence invariant |
| Non-deterministic consistency drift | #39087, #39106 | Completeness invariant (`expected == actual`) + trace record |
| Semantic inversion across library boundaries | #39052, #39047 | Behavioral invariant probe (not just type checking) |
| Internal metadata leaking to wire protocol | #39100, #39113 | Outbound payload contract at a single checkpoint |

The pattern across all of them: **the contract exists, but only as convention.** APM won't catch these. Type systems won't catch these. Schema validation won't catch most of these — the value is often perfectly well-typed and perfectly wrong.

---

## What's next

- Build log #2: the full `#39163` autopsy, including why the terminal-state invariant is harder than it looks (cancellation is a legitimate terminal state, not a failure — count it, don't trip the breaker on it).
- Weekly diagnostic digests, published as they're written.
- Diagnostic pipeline automation: self-serve upload → automated analysis.

If you maintain an agent framework or an adapter and want an outside autopsy on a specific issue, the pipeline is free and the reports are public. Open an issue on the repo.

---

**ARK — Agent Reliability Kit.** MIT licensed. Trust infrastructure for AI agents.

[GitHub](https://github.com/wzg0911/ark) · [PyPI `ark-trust`](https://pypi.org/project/ark-trust/) · [npm `@feilunxitong/arkit`](https://www.npmjs.com/package/@feilunxitong/arkit) · Go: `go get github.com/wzg0911/ark-go`

*Defect pattern index (23 reports / 10 families): [`docs/reports/ark-defect-pattern-index.md`](https://github.com/wzg0911/ark/blob/main/docs/reports/ark-defect-pattern-index.md)*
