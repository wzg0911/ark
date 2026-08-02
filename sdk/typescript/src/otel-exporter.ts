/**
 * ARK OpenTelemetry 导出器 (TypeScript) — v0.6.0
 *
 * 零依赖 OTLP/JSON 导出器，把 ARK 可靠性事件推送到
 * Jaeger / Langfuse / Tempo / Zipkin / 任何 OTLP 兼容后端
 *
 * 设计原则（与 Python 版对齐）：
 *  1. 零依赖：纯 fetch 实现 OTLP/JSON over HTTP
 *  2. 零侵入：未配置 endpoint 时所有 emit() 是 no-op（一次 if 判断）
 *  3. 批量缓冲：100 条/批 或 5 秒刷新（降低 collector 压力）
 *  4. 8 种事件类型：idempotency.hit/miss, circuit.open/close/half_open,
 *     validation.fail/pass, guardian.intercept
 *
 * 用法：
 *   const exporter = new OTelExporter({ endpoint: 'http://localhost:4318/v1/events' });
 *   exporter.emit({
 *     eventType: 'ark.circuit.open',
 *     traceId: 'abc123',
 *     spanId: 'def456',
 *     toolName: 'web_search',
 *   });
 *
 * 或零配置（环境变量）：
 *   process.env.ARK_OTEL_ENDPOINT = 'http://collector:4318/v1/events';
 *   const exporter = new OTelExporter();
 */

export type ArkEventType =
  | 'ark.idempotency.hit'
  | 'ark.idempotency.miss'
  | 'ark.circuit.open'
  | 'ark.circuit.close'
  | 'ark.circuit.half_open'
  | 'ark.validation.fail'
  | 'ark.validation.pass'
  | 'ark.guardian.intercept';

export interface ReliabilityEvent {
  eventType: ArkEventType;
  traceId: string;
  spanId: string;
  toolName: string;
  timestampNs?: number;
  durationMs?: number;
  error?: string;
  attributes?: Record<string, string | number | boolean | string[]>;
}

export interface OTelExporterOptions {
  endpoint?: string;
  serviceName?: string;
  serviceVersion?: string;
  batchSize?: number;
  flushIntervalMs?: number;
  enabled?: boolean;
}

interface OtlpAttributeValue {
  stringValue?: string;
  intValue?: string;
  doubleValue?: number;
  boolValue?: boolean;
  arrayValue?: { values: OtlpAttributeValue[] };
}

export function toOtlpValue(v: unknown): OtlpAttributeValue {
  if (typeof v === 'boolean') return { boolValue: v };
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return { intValue: String(v) };
    return { doubleValue: v };
  }
  if (Array.isArray(v)) {
    return { arrayValue: { values: v.map(toOtlpValue) } };
  }
  return { stringValue: String(v) };
}

function toOtlp(event: ReliabilityEvent, serviceName: string, serviceVersion: string) {
  const ts = event.timestampNs ?? Date.now() * 1_000_000;
  const durNs = event.durationMs != null ? Math.round(event.durationMs * 1_000_000) : 0;
  const isError = !!event.error || event.eventType === 'ark.validation.fail';
  return {
    resourceSpans: [
      {
        resource: {
          attributes: [
            { key: 'service.name', value: { stringValue: serviceName } },
            { key: 'service.version', value: { stringValue: serviceVersion } },
            { key: 'telemetry.sdk.name', value: { stringValue: 'ark-trust' } },
          ],
        },
        scopeSpans: [
          {
            scope: { name: 'ark.reliability', version: serviceVersion },
            spans: [
              {
                traceId: event.traceId.padStart(32, '0'),
                spanId: event.spanId.padStart(16, '0'),
                name: event.eventType,
                kind: 1, // INTERNAL
                startTimeUnixNano: String(ts),
                endTimeUnixNano: String(ts + durNs),
                status: {
                  code: isError ? 2 : 1, // ERROR : OK
                  message: event.error || '',
                },
                attributes: Object.entries(event.attributes ?? {}).map(([k, v]) => ({
                  key: k,
                  value: toOtlpValue(v),
                })),
              },
            ],
          },
        ],
      },
    ],
  };
}

export class OTelExporter {
  private readonly endpoint: string;
  private readonly serviceName: string;
  private readonly serviceVersion: string;
  private readonly batchSize: number;
  private readonly flushIntervalMs: number;
  private readonly enabled: boolean;
  private buffer: ReliabilityEvent[] = [];
  private timer: ReturnType<typeof setInterval> | null = null;
  private flushing = false;

  constructor(opts: OTelExporterOptions = {}) {
    this.endpoint = opts.endpoint ?? process.env.ARK_OTEL_ENDPOINT ?? '';
    this.serviceName = opts.serviceName ?? 'ark';
    this.serviceVersion = opts.serviceVersion ?? '0.6.0';
    this.batchSize = opts.batchSize ?? 100;
    this.flushIntervalMs = opts.flushIntervalMs ?? 5000;
    this.enabled = (opts.enabled ?? true) && Boolean(this.endpoint);

    if (this.enabled) {
      this.timer = setInterval(() => {
        void this.flush();
      }, this.flushIntervalMs);
      // 防止 Node 进程被 timer 阻塞退出
      if (typeof this.timer === 'object' && this.timer && 'unref' in this.timer) {
        (this.timer as { unref: () => void }).unref();
      }
    }
  }

  /** Emit 单条事件；未启用时为 no-op */
  emit(event: ReliabilityEvent): void {
    if (!this.enabled) return;
    this.buffer.push(event);
    if (this.buffer.length >= this.batchSize) {
      void this.flush();
    }
  }

  /** 强制刷新缓冲区 */
  async flush(): Promise<void> {
    if (this.flushing || this.buffer.length === 0 || !this.enabled) return;
    this.flushing = true;
    const batch = this.buffer.splice(0, this.batchSize);
    const payload = {
      ...toOtlp(batch[0]!, this.serviceName, this.serviceVersion),
      // 实际 OTLP 协议要求单次 payload 包含多个 spans，
      // 简化起见：每个事件独立 POST（保持零依赖 + 简单）
    };
    try {
      // 批量：合并到一个 resourceSpans 中
      const merged = {
        resourceSpans: [
          {
            resource: payload.resourceSpans[0]!.resource,
            scopeSpans: [
              {
                scope: payload.resourceSpans[0]!.scopeSpans[0]!.scope,
                spans: batch.map((e) => {
                  const single = toOtlp(e, this.serviceName, this.serviceVersion);
                  return single.resourceSpans[0]!.scopeSpans[0]!.spans[0]!;
                }),
              },
            ],
          },
        ],
      };
      const res = await fetch(this.endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(merged),
      });
      if (!res.ok) {
        // 失败时回写 buffer 前部，避免丢失
        this.buffer.unshift(...batch);
      }
    } catch {
      this.buffer.unshift(...batch);
    } finally {
      this.flushing = false;
    }
  }

  /** 关闭：flush + 清理 timer */
  async close(): Promise<void> {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    await this.flush();
  }

  /** 当前缓冲区大小（用于测试/监控） */
  get pendingCount(): number {
    return this.buffer.length;
  }

  get isEnabled(): boolean {
    return this.enabled;
  }
}
