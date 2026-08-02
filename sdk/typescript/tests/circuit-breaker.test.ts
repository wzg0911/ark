import { describe, it, expect } from 'vitest';
import { CircuitBreaker } from '../src/circuit-breaker';

describe('CircuitBreaker', () => {
  it('starts in closed state', () => {
    const cb = new CircuitBreaker('test', { failureThreshold: 3 });
    expect(cb.stats.state).toBe('closed');
    expect(cb.stats.failureCount).toBe(0);
  });

  it('opens after threshold failures', async () => {
    const cb = new CircuitBreaker('flaky', { failureThreshold: 2, timeoutMs: 60000 });
    const failing = async () => { throw new Error('fail'); };

    // First failure → still closed
    await expect(cb.call(failing, () => 'fallback')).resolves.toBe('fallback');
    expect(cb.stats.state).toBe('closed');

    // Second failure → opens
    await expect(cb.call(failing, () => 'fallback')).resolves.toBe('fallback');
    expect(cb.stats.state).toBe('open');
    expect(cb.stats.failureCount).toBe(2);
  });

  it('blocks all calls when open', async () => {
    const cb = new CircuitBreaker('blocked', { failureThreshold: 1, timeoutMs: 60000 });
    const failing = async () => { throw new Error('fail'); };
    await cb.call(failing, () => 'f1');

    // Now open — no fallback should throw
    await expect(cb.call(failing)).rejects.toThrow('CircuitBreaker');
  });

  it('enters half-open after timeout and recovers', async () => {
    const cb = new CircuitBreaker('recovery', { failureThreshold: 1, timeoutMs: 100 });
    const failing = async () => { throw new Error('fail'); };
    await cb.call(failing, () => 'f1');

    expect(cb.stats.state).toBe('open');

    // Wait for timeout
    await new Promise(r => setTimeout(r, 150));

    // Half-open: primary succeeds → closes
    const okay = async () => 'success';
    const result = await cb.call(okay, () => 'fallback');
    expect(result).toBe('success');
    expect(cb.stats.state).toBe('closed');
  });

  it('transitions via events', async () => {
    const cb = new CircuitBreaker('events', { failureThreshold: 1, timeoutMs: 100 });
    await cb.call(async () => { throw new Error('fail'); }, () => 'fb');

    const events = cb.getEvents();
    const openEvent = events.find(e => e.type === 'ark.circuit.open');
    expect(openEvent).toBeDefined();
    expect(openEvent!.key).toBe('events');
  });

  it('resets state', () => {
    const cb = new CircuitBreaker('reset', { failureThreshold: 1, timeoutMs: 60000 });
    cb.reset();
    expect(cb.stats.state).toBe('closed');
    expect(cb.stats.failureCount).toBe(0);
    expect(cb.stats.successCount).toBe(0);
  });
});
