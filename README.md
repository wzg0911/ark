# ARK — Agent Reliability Kit 🛡

> **Trust infrastructure for AI agents.**
> Stripe-level idempotency × Sentinel circuit breakers × OpenTelemetry tracing × IDE-style validation.
> For AI agents.

[![Tests](https://img.shields.io/badge/tests-28/28-green)](https://github.com/wzg0911/ark)
[![Python](https://img.shields.io/badge/python-3.9+-blue)](https://pypi.org)
[![License](https://img.shields.io/badge/license-MIT-purple)](LICENSE)

---

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

## 📜 License

MIT — Free forever. ARK is open infrastructure.

---

**Built with 🧬 gene recombination: Stripe × Sentinel × OpenTelemetry × IDE**
