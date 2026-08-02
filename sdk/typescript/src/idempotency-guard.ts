import { v4 as uuidv4 } from 'uuid';
import { ArkEvent, RetryOpts } from './types';

interface CacheEntry {
  key: string;
  result: unknown;
  timestamp: number;
}

/**
 * 🛡 IdempotencyGuard — Prevents duplicate tool execution.
 *
 * Every function call is assigned a unique idempotency key.
 * If the same key is used again, the cached result is returned
 * and a duplicate payment / double-send is blocked.
 *
 * Usage:
 * ```ts
 * const guard = new IdempotencyGuard();
 *
 * // First call → executes
 * const r1 = await guard.execute(() => charge(99.99), 'charge_99');
 *
 * // Second call with same key → returns cached result, no duplicate!
 * const r2 = await guard.execute(() => charge(99.99), 'charge_99');
 * ```
 */
export class IdempotencyGuard {
  private cache = new Map<string, CacheEntry>();
  private ttlMs: number;
  private events: ArkEvent[] = [];

  constructor(ttlMs: number = 24 * 60 * 60 * 1000) {
    this.ttlMs = ttlMs;
  }

  generateKey(): string {
    return uuidv4();
  }

  async execute<T>(
    fn: () => Promise<T> | T,
    key?: string,
    options?: { ttlMs?: number; toolName?: string }
  ): Promise<{ result: T; cached: boolean }> {
    const idempotencyKey = key || this.generateKey();
    const cached = this.cache.get(idempotencyKey);

    if (cached && Date.now() - cached.timestamp < this.ttlMs) {
      this.emit({
        type: 'ark.guardian.intercept',
        key: idempotencyKey,
        toolName: options?.toolName,
        timestamp: Date.now(),
      });
      return { result: cached.result as T, cached: true };
    }

    this.emit({
      type: 'ark.idempotency.miss',
      key: idempotencyKey,
      toolName: options?.toolName,
      timestamp: Date.now(),
    });

    const result = await fn();

    this.cache.set(idempotencyKey, {
      key: idempotencyKey,
      result,
      timestamp: Date.now(),
    });

    return { result, cached: false };
  }

  /** Convenience decorator-style wrapper */
  wrap<TArgs extends unknown[], TResult>(
    fn: (...args: TArgs) => Promise<TResult> | TResult,
    keyFn?: (...args: TArgs) => string
  ): (...args: TArgs) => Promise<{ result: TResult; cached: boolean }> {
    return async (...args: TArgs) => {
      const key = keyFn ? keyFn(...args) : this.generateKey();
      return this.execute(() => fn(...args), key);
    };
  }

  clear(key?: string): void {
    if (key) {
      this.cache.delete(key);
    } else {
      this.cache.clear();
    }
  }

  get stats(): { size: number; entries: string[] } {
    return {
      size: this.cache.size,
      entries: Array.from(this.cache.keys()),
    };
  }

  getEvents(): ArkEvent[] {
    return this.events;
  }

  private emit(event: ArkEvent): void {
    this.events.push(event);
  }
}
