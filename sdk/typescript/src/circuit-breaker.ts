import { ArkEvent, CircuitBreakerOpts, CircuitBreakerStats, CircuitState } from './types';

/**
 * ⚡ CircuitBreaker — Auto-meltdown → safe fallback.
 *
 * When a service fails `failureThreshold` times consecutively,
 * the circuit opens and all subsequent calls return fallback.
 * After `timeoutMs`, it enters half-open mode for recovery probe.
 *
 * Usage:
 * ```ts
 * const breaker = new CircuitBreaker('gpt-4', { failureThreshold: 3 });
 *
 * const result = await breaker.call(
 *   () => gpt4.generate(prompt),        // primary
 *   () => claude.generate(prompt),       // fallback
 * );
 * ```
 */
export class CircuitBreaker {
  readonly name: string;
  state: CircuitState = 'closed';
  failureCount = 0;
  successCount = 0;
  lastFailureTime: number | null = null;
  lastSuccessTime: number | null = null;

  private readonly failureThreshold: number;
  private readonly successThreshold: number;
  private readonly timeoutMs: number;
  private events: ArkEvent[] = [];

  constructor(name: string, opts: CircuitBreakerOpts) {
    this.name = name;
    this.failureThreshold = opts.failureThreshold;
    this.successThreshold = opts.successThreshold ?? 1;
    this.timeoutMs = opts.timeoutMs ?? 30_000;
  }

  async call<T>(
    primary: () => Promise<T> | T,
    fallback?: () => Promise<T> | T,
  ): Promise<T> {
    if (this.state === 'open') {
      if (this.lastFailureTime && Date.now() - this.lastFailureTime > this.timeoutMs) {
        // Timeout expired → half-open (try recovery)
        this.transitionTo('half_open');
      } else {
        return this.executeFallback(fallback);
      }
    }

    try {
      const result = await primary();
      this.onSuccess();
      return result;
    } catch (err) {
      this.onFailure();
      return this.executeFallback(fallback);
    }
  }

  private executeFallback<T>(fallback?: () => Promise<T> | T): T {
    if (this.state === 'open' && !fallback) {
      throw new Error(`CircuitBreaker '${this.name}' is OPEN. All calls blocked.`);
    }
    if (!fallback) {
      throw new Error(`Primary call failed and no fallback provided for '${this.name}'`);
    }
    return fallback() as T;
  }

  private onSuccess(): void {
    this.successCount++;
    this.lastSuccessTime = Date.now();

    if (this.state === 'half_open') {
      this.successCount++;
      if (this.successCount >= this.successThreshold) {
        this.transitionTo('closed');
      }
    } else {
      this.failureCount = 0; // Reset on success
    }
  }

  private onFailure(): void {
    this.failureCount++;
    this.lastFailureTime = Date.now();
    this.successCount = 0;

    if (
      (this.state === 'closed' && this.failureCount >= this.failureThreshold) ||
      this.state === 'half_open'
    ) {
      this.transitionTo('open');
    }
  }

  private transitionTo(newState: CircuitState): void {
    const prev = this.state;
    this.state = newState;

    const eventType: ArkEvent['type'] =
      newState === 'open'
        ? 'ark.circuit.open'
        : newState === 'half_open'
          ? 'ark.circuit.half_open'
          : 'ark.circuit.close';

    this.emit({
      type: eventType,
      key: this.name,
      timestamp: Date.now(),
      metadata: { prevState: prev, failureCount: this.failureCount },
    });

    if (newState === 'closed') {
      this.failureCount = 0;
      this.successCount = 0;
    }
  }

  reset(): void {
    this.state = 'closed';
    this.failureCount = 0;
    this.successCount = 0;
    this.lastFailureTime = null;
    this.lastSuccessTime = null;
  }

  get stats(): CircuitBreakerStats {
    return {
      state: this.state,
      failureCount: this.failureCount,
      successCount: this.successCount,
      lastFailureTime: this.lastFailureTime,
    };
  }

  getEvents(): ArkEvent[] {
    return this.events;
  }

  private emit(event: ArkEvent): void {
    this.events.push(event);
  }
}
