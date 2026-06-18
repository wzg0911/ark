/**
 * ARK TypeScript SDK — Basic Usage Example
 *
 * Run: npx tsx examples/basic-usage.ts
 */

import { IdempotencyGuard, CircuitBreaker, OutputValidator } from '../src';

async function main() {
  console.log('🛡 ARK TypeScript SDK Demo\n');

  // === 1. IdempotencyGuard ===
  console.log('--- IdempotencyGuard ---');
  const guard = new IdempotencyGuard();
  const simulatePayment = async (amount: number) => {
    console.log(`  💰 Charging $${amount}...`);
    return { status: 'success', amount };
  };

  const r1 = await guard.execute(() => simulatePayment(99.99), 'payment-1');
  console.log(`  Result: cached=${r1.cached}, amount=$${(r1.result as any).amount}`);

  const r2 = await guard.execute(() => simulatePayment(99.99), 'payment-1');
  console.log(`  Result: cached=${r2.cached}, amount=$${(r2.result as any).amount}`);
  console.log(`  🛡 Duplicate blocked! Call #2 was cached.\n`);

  // === 2. CircuitBreaker ===
  console.log('--- CircuitBreaker ---');
  const breaker = new CircuitBreaker('flaky-api', { failureThreshold: 2, timeoutMs: 5000 });
  const flakyCall = async () => {
    throw new Error('Service temporarily unavailable');
  };

  for (let i = 0; i < 3; i++) {
    try {
      const result = await breaker.call(flakyCall, () => '🔁 Fallback response');
      console.log(`  Call ${i + 1}: ${result}`);
    } catch (e: any) {
      console.log(`  Call ${i + 1}: ERROR — ${e.message}`);
    }
  }
  console.log(`  State: ${breaker.stats.state}`);
  console.log(`  ⚡ Circuit opened after 2 failures — subsequent calls fast-fail.\n`);

  // === 3. OutputValidator ===
  console.log('--- OutputValidator ---');
  const validator = new OutputValidator();
  const paymentSchema = {
    amount: { type: 'number', required: true, min: 0, max: 10000 },
    txn_id: { type: 'string', required: true, pattern: '^txn_' },
    email: { type: 'string', required: true, pattern: '^[\\w.-]+@[\\w.-]+\\.\\w+$' },
  };

  const validResult = validator.validate(paymentSchema, {
    amount: 42.50,
    txn_id: 'txn_abc123',
    email: 'user@example.com',
  });
  console.log(`  Valid output: ${validResult.valid}`);

  const invalidResult = validator.validate(paymentSchema, {
    amount: -5,
    txn_id: 'bad',
    email: 'not-an-email',
  });
  console.log(`  Invalid output: ${invalidResult.valid}`);
  console.log(`  Errors: ${invalidResult.errors.join(', ')}`);
  console.log(`  🔧 ARK blocked 3 invalid fields.\n`);

  console.log('✅ Demo complete. Trust your agents with ARK.');
}

main().catch(console.error);
