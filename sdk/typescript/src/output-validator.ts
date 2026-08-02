import { ArkEvent, ValidationResult } from './types';

type Schema = Record<string, { type: string; required?: boolean; min?: number; max?: number; pattern?: string }>;

/**
 * 🔧 OutputValidator — Validates agent output against schema.
 *
 * Usage:
 * ```ts
 * const validator = new OutputValidator();
 *
 * const schema: Schema = {
 *   amount: { type: 'number', required: true, min: 0 },
 *   txn_id: { type: 'string', required: true, pattern: '^txn_' },
 *   currency: { type: 'string', required: true },
 * };
 *
 * const result = validator.validate(schema, agentOutput);
 * if (!result.valid) {
 *   console.log('ARK blocked invalid output:', result.errors);
 * }
 * ```
 */
export class OutputValidator {
  private events: ArkEvent[] = [];

  validate<T extends Record<string, unknown>>(
    schema: Schema,
    data: unknown,
  ): ValidationResult<T> {
    const errors: string[] = [];
    const now = Date.now();

    if (typeof data !== 'object' || data === null) {
      errors.push('Expected object, got ' + typeof data);
      this.emit({ type: 'ark.validation.fail', timestamp: now, errors });
      return { valid: false, data: null, errors };
    }

    const obj = data as Record<string, unknown>;

    for (const [field, def] of Object.entries(schema)) {
      const value = obj[field];

      if (def.required && (value === undefined || value === null)) {
        errors.push(`Missing required field '${field}'`);
        continue;
      }

      if (value === undefined || value === null) {
        continue; // Optional field, skip
      }

      // Type check
      const actualType = typeof value;
      if (actualType !== def.type) {
        // Special: number can be integer
        if (def.type === 'number' && actualType !== 'number') {
          errors.push(`Field '${field}': expected ${def.type}, got ${actualType}`);
          continue;
        }
        if (def.type !== actualType) {
          errors.push(`Field '${field}': expected ${def.type}, got ${actualType}`);
          continue;
        }
      }

      // Numeric bounds
      if (def.type === 'number' && typeof value === 'number') {
        if (def.min !== undefined && value < def.min) {
          errors.push(`Field '${field}': value ${value} < min ${def.min}`);
        }
        if (def.max !== undefined && value > def.max) {
          errors.push(`Field '${field}': value ${value} > max ${def.max}`);
        }
      }

      // String pattern
      if (def.type === 'string' && typeof value === 'string' && def.pattern) {
        if (!new RegExp(def.pattern).test(value)) {
          errors.push(`Field '${field}': '${value}' does not match pattern '${def.pattern}'`);
        }
      }
    }

    if (errors.length > 0) {
      this.emit({ type: 'ark.validation.fail', timestamp: now, errors });
      return { valid: false, data: null, errors };
    }

    this.emit({ type: 'ark.validation.pass', timestamp: now });
    return { valid: true, data: data as T, errors: [] };
  }

  getEvents(): ArkEvent[] {
    return this.events;
  }

  private emit(event: ArkEvent): void {
    this.events.push(event);
  }
}
