# ARK TypeScript SDK 🛡

> Trust infrastructure for AI agents — now in TypeScript.

Agent Reliability Kit for the JS/TS ecosystem. Supports Node.js 18+.

## Installation

```bash
npm install ark-trust
# or
yarn add ark-trust
# or
pnpm add ark-trust
```

## Quick Start

```typescript
import { IdempotencyGuard, CircuitBreaker, OutputValidator } from 'ark-trust';

// 🛡 Never run duplicate payments
const guard = new IdempotencyGuard();
const { result, cached } = await guard.execute(
  () => chargeToStripe(99.99),
  'unique-charge-key'
);

// ⚡ Auto-fallback when models fail
const breaker = new CircuitBreaker('gpt-4', { failureThreshold: 3 });
const result = await breaker.call(
  () => gpt4.generate(prompt),
  () => claude.generate(prompt)  // Auto-switch!
);

// 🔧 Validate agent output
const validator = new OutputValidator();
const result = validator.validate(
  { amount: { type: 'number', required: true, min: 0 } },
  agentOutput
);
```

## API

| Class | Import | Description |
|-------|--------|-------------|
| `IdempotencyGuard` | `'ark-trust'` | Prevents duplicate tool execution |
| `CircuitBreaker` | `'ark-trust'` | Auto-meltdown → safe fallback |
| `OutputValidator` | `'ark-trust'` | Validates agent output against schema |

See the Python SDK for OpenTelemetry integration — coming soon to TypeScript.

## Development

```bash
npm install
npm test       # vitest
npm run build  # tsc
```

## Status

**v0.6.0-alpha** — Initial TS port. Covers core 3 pillars. OTel bridge + framework integrations coming.
