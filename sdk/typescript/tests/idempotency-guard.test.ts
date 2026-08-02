import { describe, it, expect } from 'vitest';
import { IdempotencyGuard } from '../src/idempotency-guard';

describe('IdempotencyGuard', () => {
  it('executes function on first call', async () => {
    const guard = new IdempotencyGuard();
    let callCount = 0;

    const { result, cached } = await guard.execute(async () => {
      callCount++;
      return 'hello';
    }, 'test-key');

    expect(result).toBe('hello');
    expect(cached).toBe(false);
    expect(callCount).toBe(1);
  });

  it('returns cached result on duplicate key', async () => {
    const guard = new IdempotencyGuard();
    let callCount = 0;

    await guard.execute(async () => {
      callCount++;
      return 'first';
    }, 'dup-key');

    const { result, cached } = await guard.execute(async () => {
      callCount++;
      return 'second'; // should never execute
    }, 'dup-key');

    expect(result).toBe('first');
    expect(cached).toBe(true);
    expect(callCount).toBe(1); // still 1, second was cached
  });

  it('generates unique keys automatically', () => {
    const guard = new IdempotencyGuard();
    const key1 = guard.generateKey();
    const key2 = guard.generateKey();
    expect(key1).not.toBe(key2);
  });

  it('expires entries after TTL', async () => {
    const guard = new IdempotencyGuard(100); // 100ms TTL

    await guard.execute(() => 'data', 'ttl-key');

    // Wait for TTL to expire
    await new Promise(r => setTimeout(r, 110));

    let callCount = 0;
    const { result, cached } = await guard.execute(() => {
      callCount++;
      return 'fresh';
    }, 'ttl-key');

    expect(result).toBe('fresh');
    expect(cached).toBe(false);
    expect(callCount).toBe(1);
  });

  it('wrap() creates decorated function', async () => {
    const guard = new IdempotencyGuard();
    const fn = guard.wrap(async (x: number) => x * 2);

    const r1 = await fn(21);
    expect(r1.result).toBe(42);
    expect(r1.cached).toBe(false);

    const r2 = await fn(21); // different key, so not cached
    expect(r2.result).toBe(42);
  });

  it('emits guard events on intercept', async () => {
    const guard = new IdempotencyGuard();
    await guard.execute(() => 'x', 'event-test');
    await guard.execute(() => 'y', 'event-test');

    const events = guard.getEvents();
    expect(events.length).toBe(2);
    expect(events[0].type).toBe('ark.idempotency.miss');
    expect(events[1].type).toBe('ark.guardian.intercept');
  });

  it('supports toolName in events', async () => {
    const guard = new IdempotencyGuard();
    await guard.execute(() => 'x', 'tool-test', { toolName: 'charge_customer' });
    const events = guard.getEvents();
    expect(events[0].toolName).toBe('charge_customer');
  });
});
