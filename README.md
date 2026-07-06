# ARK Trust — 3行代码，Agent永不重复执行 🛡

> **AI Agent 信任基础设施。** 幂等守卫防重复扣款 · 熔断器自动降级 · 输出校验防假输出。pip install ark-trust，3行代码接入。

<p align="center">
  <a href="https://pypi.org/project/ark-trust/"><img src="https://img.shields.io/pypi/v/ark-trust?style=flat-square&color=blue" alt="PyPI version"></a>
  <a href="https://pypi.org/project/ark-trust/"><img src="https://img.shields.io/pypi/dm/ark-trust?style=flat-square&color=green" alt="Downloads"></a>
  <a href="https://github.com/wzg0911/ark"><img src="https://img.shields.io/github/stars/wzg0911/ark?style=flat-square" alt="GitHub stars"></a>
  <a href="https://github.com/wzg0911/ark/actions"><img src="https://img.shields.io/badge/tests-250%2B1_skip-brightgreen?style=flat-square" alt="Tests"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.9+-blue?style=flat-square" alt="Python"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-purple?style=flat-square" alt="License"></a>
  <a href="https://github.com/wzg0911/ark/issues"><img src="https://img.shields.io/badge/help-wanted-orange?style=flat-square" alt="Help Wanted"></a>
</p>

<p align="center">
  <img src="https://cdn.jsdelivr.net/gh/wzg0911/ark@main/badges/ark-trust-badge.svg" alt="ARK Trusted" width="200">
</p>

---

## 🤔 The Problem

Your AI agent says it sent an email. **Did it really?**

Your AI agent says it charged $10. **Did it charge $10… or $100?**

Your AI agent retries on failure. **Did it just fire 3 duplicate payments?**

> *"Agent does not actually invoke tools, only simulates tool usage with fabricated output"*
> — *Top agent framework bug report, 63 comments*

**Without ARK, every agent action is a trust exercise. With ARK, every agent action is provably real.**

---

## ⚡ Install & Integrate in 3 Lines

```bash
pip install ark-trust
```

```python
from ark import IdempotencyGuard, CircuitBreaker, OutputValidator

# That's it. Your agent now has payment safety, model failover, and output validation.
```

---

## 📊 ARK vs. No Protection

| Scenario | ❌ Without ARK | ✅ With ARK |
|---|---|---|
| **Duplicate payments** | Agent retries → 3 charges for 1 purchase | IdempotencyGuard blocks duplicates 2 & 3 |
| **LLM provider outage** | GPT-4 fails 6x → app crashes | CircuitBreaker auto-switches to Claude |
| **Fabricated tool calls** | Agent "claims" it sent email → no proof | OutputValidator + Trace prove real execution |
| **Malformed JSON output** | `json.loads()` crashes → context window poisoned | Schema validation catches & retries automatically |
| **Streaming null responses** | Silent failure → user sees nothing | ARK detects `None` → triggers reload |
| **Observability** | Zero visibility into agent decisions | Full OTel trace of every guard, breaker, and validation |
| **Error recovery** | 5KB stack trace floods LLM context → confused agent | Error compressed to 500 chars + structured retry |

**8847+ error issues** across the top 3 agent frameworks. ARK catches them before they become incidents.

---

## 🚀 Quick Start

### 1. Protect payments from duplicates

```python
from ark import IdempotencyGuard

guard = IdempotencyGuard()

@guard.wrap
def charge(amount: float):
    return stripe.charge(amount)

charge(99.99)  # ✅ Charged
charge(99.99)  # 🛡 Intercepted — no duplicate!
```

### 2. Auto-fallback when models fail

```python
from ark import CircuitBreaker

breaker = CircuitBreaker("gpt-4", failure_threshold=3)

result = breaker.call(
    primary=lambda: gpt4.generate(prompt),
    fallback=lambda: claude.generate(prompt)  # Auto-switch on failure
)
```

### 3. Validate agent output

```python
from ark import OutputValidator
from pydantic import BaseModel

class PaymentResult(BaseModel):
    amount: float
    txn_id: str

validator = OutputValidator()
result = validator.validate(PaymentResult, agent_output)

if not result.valid:
    print(f"ARK blocked invalid output: {result.errors}")
```

---

## 🔱 The Four Pillars

| Pillar | Inspired By | What It Does |
|---|---|---|
| 🛡 **Idempotency Guard** | Stripe's payment API | Prevents duplicate tool execution — one action, one effect |
| ⚡ **Circuit Breaker** | Sentinel / Netflix Hystrix | Detects failures → auto-switches to safe fallback |
| 🔧 **Output Validator** | IDE type-checking | Validates agent output against Pydantic schemas |
| 👁 **Trace** | OpenTelemetry | Full execution trace with 8 reliability event types |

---

## 🔌 Framework Integrations

ARK auto-detects and integrates with your existing agent stack. Zero configuration required.

| Framework | Integration | Status |
|---|---|---|
| **LangChain** | `ARKCallbackHandler` | ✅ Built-in |
| **CrewAI** | `ARKCrewCallback` | ✅ Built-in |
| **AutoGen / AG2** | Auto-detected | ✅ v0.2.0+ |
| **OpenAI SDK** | Transparent middleware | ✅ All versions |
| **Any Python agent** | `@guard.wrap` decorator | ✅ Universal |

---

## 🔭 OpenTelemetry — Full Observability in One Env Var

ARK emits 8 reliability event types to your existing observability stack. **Zero code changes.**

```bash
export ARK_OTEL_ENDPOINT="http://otel-collector:4318/v1/events"
```

| Event | Trigger |
|---|---|
| `ark.idempotency.miss` | Tool first called |
| `ark.guardian.intercept` | Duplicate call blocked |
| `ark.circuit.open` | Breaker tripped |
| `ark.circuit.half_open` | Recovery probe |
| `ark.circuit.close` | Service recovered |
| `ark.validation.pass` | Output valid |
| `ark.validation.fail` | Output invalid |

Compatible with **Langfuse, Jaeger, Grafana Tempo, Honeycomb, Datadog** — any OTLP receiver.

---

## 🩹 Self-Healing Errors (Factor 9 for AI Agents)

Your agent hits a flaky API. **What happens?**

- ❌ **Without ARK F9:** 5KB stack trace floods the LLM's context window → confused agent, wasted tokens
- ✅ **With ARK F9:** Error compressed to 500 chars + last 3 stack lines → LLM knows exactly what to fix

```python
from ark.errors import with_retry, should_retry, error_to_llm_context

# Auto-retry with exponential backoff (1s → 2s → 4s → 8s → 16s)
@with_retry(tool_name="send_email", max_attempts=3)
def send_email(to, subject):
    return smtp.send(to, subject)

# Smart retry: AuthError → skip retry immediately (save 30s)
try:
    charge_card(amount)
except AuthError as e:
    if not should_retry(e, attempt=1, max_attempts=3)[0]:
        return redirect_to_human_review()

# Feed structured error context to LLM for self-healing
try:
    call_external_api()
except Exception as e:
    prompt = error_to_llm_context(e)  # 500 chars, structured, LLM-ready
    response = llm.invoke(prompt)
```

---

## 🏗 Architecture

```
Your AI Agent (LangChain / CrewAI / Custom)
                │
                ▼
┌───────────────────────────────────────┐
│         ARK Trust Layer               │
│  ┌──────────┐  ┌──────────────┐      │
│  │🛡 Guard  │  │ ⚡ Breaker    │      │
│  │Idempotency│  │ CircuitBreak │      │
│  └──────────┘  └──────────────┘      │
│  ┌──────────┐  ┌──────────────┐      │
│  │🔧 Validate│  │ 👁 Trace     │      │
│  │Schema     │  │ OpenTelemetry│      │
│  └──────────┘  └──────────────┘      │
└───────────────────────────────────────┘
                │
                ▼
       Your Tools & APIs (Stripe, SMTP, DB, …)
```

---

## 📈 Roadmap

- [x] **v0.1** — 4 core pillars (Idempotency, Circuit Breaker, Validator, Trace)
- [x] **v0.2** — Reliability Score + Schema Registry (13 schemas)
- [x] **v0.3** — Dashboard UI + Achievement system
- [x] **v0.4** — Community Schema Hub + Benchmarks (7 baselines)
- [x] **v0.5** — OpenTelemetry export (8 event types) + Self-healing errors (F9)
- [x] **v0.5.3** — Native OTel SDK bridge (dual-emit to existing tracer)
- [x] **v0.6** — TypeScript SDK (full parity with Python SDK)
- [x] **v0.7** — Go SDK (full parity + Error F9 + SchemaHub)
- [ ] **v1.0** — Production SLA guarantees + Enterprise dashboard

---

## 💬 Community

- 💬 **[Discord](https://discord.gg/arktrust)** — Get help, share use cases, contribute
- 🐛 **[GitHub Issues](https://github.com/wzg0911/ark/issues)** — Bug reports & feature requests
- ⭐ **Star this repo** — It helps others discover ARK
- 💝 **[Sponsor ARK](https://github.com/sponsors/wzg0911)** — Keep it open-source and alive

---

## 🔥 ARK Pro — Enterprise-Grade Agent Reliability

Need more than open-source? **ARK Pro** adds:

- 🔐 **SLA-backed reliability guarantees** for production agents
- 📊 **Advanced dashboard** with multi-agent trust scoring
- 🏢 **SSO, RBAC, audit logging** for enterprise deployments
- 🎯 **Priority support** with 4-hour response SLA

<p align="center">
  <a href="https://wzg0911.github.io/ark/pro.html">
    <img src="https://img.shields.io/badge/ARK_Pro-Learn_More-ff6b35?style=for-the-badge&logo=shield" alt="ARK Pro">
  </a>
</p>

---

## 📜 License

MIT — Free forever. ARK is open infrastructure for the agent era.

---

<p align="center">
  <sub>Built with 🧬 gene recombination: Stripe × Sentinel × OpenTelemetry × IDE</sub>
</p>
