import { describe, it, expect } from 'vitest';
import { OutputValidator } from '../src/output-validator';

describe('OutputValidator', () => {
  it('passes valid data', () => {
    const v = new OutputValidator();
    const schema = {
      name: { type: 'string', required: true },
      age: { type: 'number', required: true },
    };

    const result = v.validate(schema, { name: 'Alice', age: 30 });
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
    expect(result.data).toEqual({ name: 'Alice', age: 30 });
  });

  it('rejects missing required field', () => {
    const v = new OutputValidator();
    const schema = {
      txn_id: { type: 'string', required: true },
      amount: { type: 'number', required: true },
    };

    const result = v.validate(schema, { txn_id: 'abc123' });
    expect(result.valid).toBe(false);
    expect(result.errors).toContain("Missing required field 'amount'");
  });

  it('rejects wrong type', () => {
    const v = new OutputValidator();
    const schema = {
      amount: { type: 'number', required: true },
    };

    const result = v.validate(schema, { amount: 'not-a-number' });
    expect(result.valid).toBe(false);
  });

  it('enforces numeric bounds', () => {
    const v = new OutputValidator();
    const schema = {
      amount: { type: 'number', required: true, min: 0, max: 10000 },
    };

    expect(v.validate(schema, { amount: -1 }).valid).toBe(false);
    expect(v.validate(schema, { amount: 10001 }).valid).toBe(false);
    expect(v.validate(schema, { amount: 500 }).valid).toBe(true);
  });

  it('enforces string pattern', () => {
    const v = new OutputValidator();
    const schema = {
      email: { type: 'string', required: true, pattern: '^[\\w.-]+@[\\w.-]+\\.\\w+$' },
    };

    expect(v.validate(schema, { email: 'bad' }).valid).toBe(false);
    expect(v.validate(schema, { email: 'alice@example.com' }).valid).toBe(true);
  });

  it('emits validation events', () => {
    const v = new OutputValidator();
    v.validate({ x: { type: 'string', required: true } }, { x: 'ok' });
    v.validate({ x: { type: 'number', required: true } }, { x: 'nope' });

    const events = v.getEvents();
    expect(events.length).toBe(2);
    expect(events[0].type).toBe('ark.validation.pass');
    expect(events[1].type).toBe('ark.validation.fail');
  });

  it('rejects non-object input', () => {
    const v = new OutputValidator();
    const r = v.validate({}, 'not-object');
    expect(r.valid).toBe(false);
  });
});
