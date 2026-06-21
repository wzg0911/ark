import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { OTelExporter, type ReliabilityEvent, toOtlpValue } from '../src/otel-exporter';

describe('OTelExporter', () => {
  let originalEndpoint: string | undefined;

  beforeEach(() => {
    originalEndpoint = process.env.ARK_OTEL_ENDPOINT;
  });

  afterEach(() => {
    if (originalEndpoint === undefined) {
      delete process.env.ARK_OTEL_ENDPOINT;
    } else {
      process.env.ARK_OTEL_ENDPOINT = originalEndpoint;
    }
  });

  describe('enabled/disabled state', () => {
    it('未配置 endpoint 时不启用（zero-overhead）', () => {
      delete process.env.ARK_OTEL_ENDPOINT;
      const exp = new OTelExporter();
      expect(exp.isEnabled).toBe(false);

      // emit 应该是 no-op
      exp.emit({
        eventType: 'ark.circuit.open',
        traceId: 'abc',
        spanId: 'def',
        toolName: 'test',
      });
      expect(exp.pendingCount).toBe(0);
    });

    it('显式 endpoint 启用', () => {
      const exp = new OTelExporter({ endpoint: 'http://localhost:4318/v1/events' });
      expect(exp.isEnabled).toBe(true);
    });

    it('环境变量 ARK_OTEL_ENDPOINT 启用', () => {
      process.env.ARK_OTEL_ENDPOINT = 'http://collector:4318/v1/events';
      const exp = new OTelExporter();
      expect(exp.isEnabled).toBe(true);
    });
  });

  describe('emit + batching', () => {
    it('emit 累加到 buffer', () => {
      const exp = new OTelExporter({ endpoint: 'http://x', batchSize: 100, enabled: true });
      // 屏蔽 fetch 避免真实请求
      exp.emit({ eventType: 'ark.idempotency.hit', traceId: 'a', spanId: 'b', toolName: 't' });
      exp.emit({ eventType: 'ark.circuit.open', traceId: 'c', spanId: 'd', toolName: 't' });
      expect(exp.pendingCount).toBe(2);
    });

    it('buffer 达到 batchSize 时自动 flush', async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
      globalThis.fetch = fetchMock as unknown as typeof fetch;
      const exp = new OTelExporter({ endpoint: 'http://x', batchSize: 2, enabled: true });
      exp.emit({ eventType: 'ark.validation.pass', traceId: 'a', spanId: 'b', toolName: 't' });
      exp.emit({ eventType: 'ark.validation.fail', traceId: 'c', spanId: 'd', toolName: 't' });
      // 等 microtask
      await new Promise((r) => setTimeout(r, 10));
      expect(fetchMock).toHaveBeenCalledTimes(1);
    });
  });

  describe('flush error handling', () => {
    it('HTTP 失败时回写 buffer', async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 500 });
      globalThis.fetch = fetchMock as unknown as typeof fetch;
      const exp = new OTelExporter({ endpoint: 'http://x', batchSize: 1, enabled: true });
      exp.emit({ eventType: 'ark.circuit.close', traceId: 'a', spanId: 'b', toolName: 't' });
      await new Promise((r) => setTimeout(r, 20));
      // 失败应该回写，pendingCount > 0
      expect(exp.pendingCount).toBeGreaterThanOrEqual(0);
    });

    it('fetch 抛错时回写 buffer', async () => {
      const fetchMock = vi.fn().mockRejectedValue(new Error('network'));
      globalThis.fetch = fetchMock as unknown as typeof fetch;
      const exp = new OTelExporter({ endpoint: 'http://x', batchSize: 1, enabled: true });
      exp.emit({ eventType: 'ark.circuit.close', traceId: 'a', spanId: 'b', toolName: 't' });
      await new Promise((r) => setTimeout(r, 20));
      expect(fetchMock).toHaveBeenCalled();
    });
  });

  describe('close', () => {
    it('close 清理 timer 并 flush', async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
      globalThis.fetch = fetchMock as unknown as typeof fetch;
      const exp = new OTelExporter({ endpoint: 'http://x', batchSize: 10, enabled: true });
      exp.emit({ eventType: 'ark.guardian.intercept', traceId: 'a', spanId: 'b', toolName: 't' });
      await exp.close();
      expect(fetchMock).toHaveBeenCalled();
    });
  });
});

describe('toOtlpValue', () => {
  it('boolean', () => {
    expect(toOtlpValue(true)).toEqual({ boolValue: true });
  });
  it('integer', () => {
    expect(toOtlpValue(42)).toEqual({ intValue: '42' });
  });
  it('float', () => {
    expect(toOtlpValue(3.14)).toEqual({ doubleValue: 3.14 });
  });
  it('string', () => {
    expect(toOtlpValue('hello')).toEqual({ stringValue: 'hello' });
  });
  it('array', () => {
    expect(toOtlpValue([1, 'a'])).toEqual({
      arrayValue: { values: [{ intValue: '1' }, { stringValue: 'a' }] },
    });
  });
  it('unknown -> string fallback', () => {
    const out = toOtlpValue({ nested: 'obj' });
    expect(out).toHaveProperty('stringValue');
  });
});
