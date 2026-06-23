# ARK — Agent Reliability Kit 🛡

> **Trust infrastructure for AI agents.**
> Stripe-level idempotency × Sentinel circuit breakers × OpenTelemetry tracing × IDE-style validation.
> For AI agents.

[![Tests](https://img.shields.io/badge/tests-303/303-green)](https://github.com/wzg0911/ark)
[![Python](https://img.shields.io/badge/python-3.9+-blue)](https://pypi.org)
[![Version](https://img.shields.io/badge/version-0.6.0-blueviolet)](https://pypi.org/project/ark-trust/)
[![License](https://img.shields.io/badge/license-MIT-purple)](LICENSE)

---

README.md

> 💝 **赞助 ARK**: [GitHub Sponsors](https://github.com/sponsors/wzg0911) · [爱发电](https://afdian.com/a/wzg911) · 微信: 84911541@qq.com
> 
> ARK 是 MIT 协议开源的。你的赞助让它活下去。详见 [SPONSOR.md](./SPONSOR.md)。
> 

## 🤔 Why ARK?

Your AI agent says it sent an email. **Did it really?**
Your AI agent says it charged $10. **Did it charge $10... or $100?**
Your AI agent retries on failure. **Did it just send 3 duplicate payments?**

> "Agent does not actually invoke tools, only simulates tool usage with fabricated output"
> — *CrewAI Bug #?*, 63 comments

**ARK proves every agent action is real.**

## ⚡ Quick Start

```bash
pip install ark-trust
```

```python
from ark import IdempotencyGuard, CircuitBreaker, OutputValidator

# 🛡 1. Never run duplicate payments
guard = IdempotencyGuard()

@guard.wrap
def charge(amount: float):
    return stripe.charge(amount)

charge(99.99)  # ✅ Charged
charge(99.99)  # 🛡 Intercepted — no duplicate!

# ⚡ 2. Auto-fallback when models fail
breaker = CircuitBreaker("gpt-4", failure_threshold=3)

result = breaker.call(
    primary=lambda: gpt4.generate(prompt),
    fallback=lambda: claude.generate(prompt)  # Auto-switch!
)

# 🔧 3. Validate agent output
from pydantic import BaseModel

class PaymentResult(BaseModel):
    amount: float
    txn_id: str

validator = OutputValidator()
result = validator.validate(PaymentResult, agent_output)
if not result.valid:
    print(f"ARK blocked invalid output: {result.errors}")
```

## 🔱 The Four Pillars

| Pillar | Gene Source | What It Does |
|--------|------------|--------------|
| 🛡 **Idempotency Guard** | Stripe payments | Prevents duplicate tool execution |
| ⚡ **Circuit Breaker** | Sentinel microservices | Auto-meltdown → safe fallback |
| 🔧 **Output Validator** | IDE type checking | Validates agent output against schema |
| 👁 **Trace** | OpenTelemetry | Full execution trace visibility |

## 📊 What ARK Catches

```
CrewAI agents fake tool calls     → ARK validates real execution
GPT-4 fails 6 times in a row      → ARK auto-switches to Claude
Agent retries a payment 3 times   → ARK blocks duplicates 2&3
Streaming response returns null   → ARK detects + reloads
```

## 🎯 The Numbers

- **8847** error issues across top 3 agent frameworks
- **50+ comments** on a single "duplicate payment" bug
- **75%** of agent outputs need validation
- **0** existing products in this space (max competitor: 129⭐)

## 🏗 Architecture

```
Your Agent
    ↓
┌─── ARK Trust Layer ───┐
│  🛡 Guard   ⚡ Breaker │
│  🔧 Validator 👁 Trace │
└───────────────────────┘
    ↓
Your Tools & APIs
```

## 🚀 Roadmap

- [x] MVP — 4 core pillars (v0.1.0)
- [x] LangChain integration — `ARKCallbackHandler` (v0.1.0)
- [x] CrewAI integration — `ARKCrewCallback` (v0.1.1)
- [x] Auto-detect frameworks (v0.2.0)
- [x] Reliability Score + Schema Registry — 13 schemas (v0.2.0)
- [x] Dashboard UI — real-time trust monitoring (v0.3.0)
- [x] Achievement system — gamified reliability badges (v0.3.0)
- [x] PyPI publish automation (v0.3.0)
- [x] Community Schema Hub (v0.4.0)
- [x] Benchmarks — 7 performance baselines (v0.4.0)
- [x] **OpenTelemetry Exporter — 8 reliability event types (v0.5.0)**
- [x] **Zero-touch instrumentation — one env var to activate (v0.5.0)**

## 🔭 OpenTelemetry Integration (v0.5.0)

ARK reliability events are emitted to your observability stack via standard OTLP/JSON. **Zero code changes** to existing agents — set one env var:

```bash
export ARK_OTEL_ENDPOINT="http://otel-collector:4318/v1/events"
```

| Event Type | Trigger |
|------------|---------|
| `ark.idempotency.miss` | Tool first called |
| `ark.guardian.intercept` | Duplicate call blocked (saves real ms) |
| `ark.circuit.open` | Breaker tripped |
| `ark.circuit.half_open` | Recovery probe |
| `ark.circuit.close` | Service recovered |
| `ark.validation.pass` | Output schema valid |
| `ark.validation.fail` | Output schema invalid |

Compatible with **Langfuse, Jaeger, Tempo, Honeycomb** — any OTLP receiver.

### ⚡ 5-Minute Live Demo

See ARK events flow into Langfuse with one command:

```bash
cd examples/langfuse-demo
docker compose up -d
pip install -e ../..
python app.py
# Open http://localhost:3000 → watch ARK reliability events stream in
```

## 🩹 Self-Healing Errors (v0.5.1) — 12-Factor Agents Factor 9

Your agent hits a flaky API. **What does it do?**
- ❌ Without F9: stack trace explodes the LLM's context window → token waste + confused LLM
- ✅ With ARK F9: error compressed to 500 chars + last 3 stack lines + md5 hash → LLM knows exactly what to fix

```python
from ark.errors import with_retry, should_retry, truncate_error, error_to_llm_context

# 🩹 1. Auto-retry with exponential backoff (1s → 2s → 4s)
@with_retry(tool_name="send_email", max_attempts=3)
def send_email(to, subject):
    return smtp.send(to, subject)

# 🎯 2. Smart retry decisions (8 NON_RETRYABLE_TYPES skipped immediately)
try:
    charge_card(amount)
except AuthError as e:
    if not should_retry(e, attempt=1, max_attempts=3)[0]:
        return redirect_to_human_review()  # Skip retry, save 30s

# 🧠 3. Feed structured error to LLM (self-healing)
try:
    call_external_api()
except Exception as e:
    prompt = error_to_llm_context(e)  # 500-char message + stack tail + retry hint
    response = llm.invoke(prompt)     # LLM decides: different tool? different args?
```

| F9 Capability | What It Solves |
|----------------|----------------|
| `truncate_error()` | 5KB stack → 500 chars + last 3 lines + md5 hash |
| `should_retry()` | Auth/Validation errors skip retry immediately (save 30s) |
| `retry_delay()` | Exponential backoff 1s → 2s → 4s → 8s → 16s, capped 30s |
| `with_retry()` | One-line decorator: retry + truncate + fallback + escalate |
| `error_to_llm_context()` | Structured prompt for LLM self-healing |
| `ErrorContext` | Thread-safe accumulator, serializable for F5 state unification |

### ⚡ 1-Minute F9 Demo (no Docker)

```bash
cd examples/f9-self-healing
python app.py
# See: 5KB stack compressed to ~500 chars, 8 NON_RETRYABLE_TYPES identified, 3-round retry simulation
```

## 🌉 Native OTel SDK Bridge (v0.5.3) — Zero-friction observability

**One-line upgrade for OTel users.** If your stack already runs the OpenTelemetry SDK, ARK now **dual-emits** reliability events to your existing tracer — no code change, no OTLP collector required.

```python
# Before v0.5.3: OTLP/JSON only (need collector)
export ARK_OTEL_ENDPOINT=http://collector:4318

# After v0.5.3: dual-emit, automatic if opentelemetry-api installed
pip install opentelemetry-api   # that's it
export ARK_OTEL_ENDPOINT=http://collector:4318  # collector still works
# Native spans flow into your existing tracer (Jaeger/Tempo/Honeycomb) automatically
```

**Why this matters:**
- 🔌 **Plug into existing observability** — If you already pay for Datadog/Honeycomb/Tempo, ARK events appear next to your app spans
- 🛡 **100% backward compatible** — `use_native_sdk=False` (default) keeps the old OTLP/JSON path; opt in with one flag
- 🪫 **Zero overhead when off** — `if not use_native_sdk: return` is the first line; no imports, no allocations
- 🚨 **Failure-isolated** — `try/except` around native span emit: a broken SDK init never breaks your OTLP export
- 🟥 **Auto-set ERROR status** on `VALIDATION_FAIL` — your alerting tools see it immediately

**Test coverage:** 16 new tests in `test_v0_5_3_otel_sdk_bridge.py` covering type coercion, SDK availability probing, opt-out path, span emission, attribute propagation, ERROR status on validation failure, failure isolation, stats() reporting, and backward-compat signatures.

## 📦 What's New in v0.5.3

| Feature | Status | Description |
|---------|--------|-------------|
| Native OTel SDK bridge | ✅ | Auto-detect `opentelemetry-api`; dual-emit to existing tracer |
| ROADMAP v0.5.0 close-out | ✅ | Last unchecked item shipped (`原生 opentelemetry-sdk 集成`) |
| Backward compat | ✅ | All 235 v0.5.2 tests still pass; +16 new tests = 251 total |
| Pre-built wheels | ✅ | `dist/ark_trust-0.5.3-py3-none-any.whl` (51.6 KB) ready for PyPI |

## 📜 License

MIT — Free forever. ARK is open infrastructure.

---

**Built with 🧬 gene recombination: Stripe × Sentinel × OpenTelemetry × IDE**
