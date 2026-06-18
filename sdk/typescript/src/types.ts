/** ARK event types emitted to observability */

export type ArkEventType =
  | 'ark.idempotency.miss'
  | 'ark.idempotency.hit'
  | 'ark.guardian.intercept'
  | 'ark.circuit.open'
  | 'ark.circuit.half_open'
  | 'ark.circuit.close'
  | 'ark.validation.pass'
  | 'ark.validation.fail';

export interface ArkEvent {
  type: ArkEventType;
  timestamp: number; // epoch ms
  toolName?: string;
  key?: string;
  durationMs?: number;
  errors?: string[];
  metadata?: Record<string, unknown>;
}

/** Circuit Breaker state machine */
export type CircuitState = 'closed' | 'open' | 'half_open';

export interface CircuitBreakerOpts {
  failureThreshold: number;
  successThreshold?: number;
  timeoutMs?: number;
}

export interface CircuitBreakerStats {
  state: CircuitState;
  failureCount: number;
  successCount: number;
  lastFailureTime: number | null;
}

export interface RetryOpts {
  maxAttempts: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
}

export interface ValidationResult<T = unknown> {
  valid: boolean;
  data: T | null;
  errors: string[];
}
