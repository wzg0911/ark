// Package ark — OpenTelemetry exporter for reliability events.
//
// OTelExporter emits ARK reliability events (idempotency hit/miss,
// circuit open/close/half_open, validation pass/fail, guardian intercept)
// as OTLP/JSON to any OTel Collector (Jaeger, Langfuse, Tempo, etc).
//
// Design:
//  1. Zero-dependency: pure stdlib (net/http + encoding/json)
//  2. Ring-buffer batching: flush on batch_size or interval
//  3. Optional: auto-activated by ARK_OTEL_ENDPOINT env var
//  4. Singleton: GetOTelExporter() for global instance
package ark

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/wzg0911/ark-go/internal/buffer"
)

// ArkEventType represents ARK reliability event types.
type ArkEventType string

const (
	EventIdempotencyHit    ArkEventType = "ark.idempotency.hit"
	EventIdempotencyMiss   ArkEventType = "ark.idempotency.miss"
	EventCircuitOpen       ArkEventType = "ark.circuit.open"
	EventCircuitClose      ArkEventType = "ark.circuit.close"
	EventCircuitHalfOpen   ArkEventType = "ark.circuit.half_open"
	EventValidationFail    ArkEventType = "ark.validation.fail"
	EventValidationPass    ArkEventType = "ark.validation.pass"
	EventGuardianIntercept ArkEventType = "ark.guardian.intercept"
)

// AllEventTypes returns all 8 event types for iteration.
func AllEventTypes() []ArkEventType {
	return []ArkEventType{
		EventIdempotencyHit, EventIdempotencyMiss,
		EventCircuitOpen, EventCircuitClose, EventCircuitHalfOpen,
		EventValidationFail, EventValidationPass,
		EventGuardianIntercept,
	}
}

// ReliabilityEvent is a single ARK reliability event.
type ReliabilityEvent struct {
	EventType   ArkEventType       `json:"event_type"`
	TimestampNs int64              `json:"timestamp_ns"`
	TraceID     string             `json:"trace_id"`
	SpanID      string             `json:"span_id"`
	ToolName    string             `json:"tool_name"`
	Attributes  map[string]string  `json:"attributes"`
	DurationMs  *float64           `json:"duration_ms,omitempty"`
	Error       *string            `json:"error,omitempty"`
}

// otlpSpan is the OTLP JSON span representation.
type otlpSpan struct {
	TraceID           string          `json:"traceId"`
	SpanID            string          `json:"spanId"`
	Name              string          `json:"name"`
	Kind              int             `json:"kind"`
	StartTimeUnixNano string          `json:"startTimeUnixNano"`
	EndTimeUnixNano   string          `json:"endTimeUnixNano"`
	Status            otlpStatus      `json:"status"`
	Attributes        []otlpAttribute `json:"attributes"`
}

type otlpStatus struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type otlpAttribute struct {
	Key   string      `json:"key"`
	Value otlpValue   `json:"value"`
}

type otlpValue struct {
	StringValue  *string       `json:"stringValue,omitempty"`
	IntValue     *string       `json:"intValue,omitempty"`
	DoubleValue  *float64      `json:"doubleValue,omitempty"`
	BoolValue    *bool         `json:"boolValue,omitempty"`
	ArrayValue   *otlpArray    `json:"arrayValue,omitempty"`
}

type otlpArray struct {
	Values []otlpValue `json:"values"`
}

type otlpResourceSpan struct {
	Resource   otlpResource    `json:"resource"`
	ScopeSpans []otlpScopeSpan `json:"scopeSpans"`
}

type otlpResource struct {
	Attributes []otlpAttribute `json:"attributes"`
}

type otlpScopeSpan struct {
	Scope otlpScope  `json:"scope"`
	Spans []otlpSpan `json:"spans"`
}

type otlpScope struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

type otlpPayload struct {
	ResourceSpans []otlpResourceSpan `json:"resourceSpans"`
}

// ToOTLP converts the event to OTLP/JSON payload.
func (e *ReliabilityEvent) ToOTLP(serviceName string) *otlpPayload {
	severityCode := 1 // OK
	errMsg := ""
	if e.Error != nil {
		severityCode = 2
		errMsg = *e.Error
	}
	if e.EventType == EventValidationFail {
		severityCode = 2
		if errMsg == "" {
			errMsg = string(EventValidationFail)
		}
	}

	endNs := e.TimestampNs
	if e.DurationMs != nil {
		endNs += int64(*e.DurationMs * 1_000_000)
	}

	attrs := make([]otlpAttribute, 0, len(e.Attributes)+2)
	attrs = append(attrs, otlpAttribute{
		Key:   "ark.tool_name",
		Value: toOTLPValue(e.ToolName),
	})
	attrs = append(attrs, otlpAttribute{
		Key:   "ark.event_type",
		Value: toOTLPValue(string(e.EventType)),
	})
	for k, v := range e.Attributes {
		attrs = append(attrs, otlpAttribute{
			Key:   fmt.Sprintf("ark.%s", k),
			Value: toOTLPValue(v),
		})
	}

	// Pad trace/span IDs to OTLP spec lengths.
	traceID := e.TraceID
	for len(traceID) < 32 {
		traceID = "0" + traceID
	}
	spanID := e.SpanID
	for len(spanID) < 16 {
		spanID = "0" + spanID
	}

	return &otlpPayload{
		ResourceSpans: []otlpResourceSpan{{
			Resource: otlpResource{
				Attributes: []otlpAttribute{
					{Key: "service.name", Value: otlpValue{StringValue: &serviceName}},
					{Key: "service.version", Value: otlpValue{StringValue: strPtr(Version)}},
					{Key: "telemetry.sdk.name", Value: otlpValue{StringValue: strPtr("ark-trust")}},
				},
			},
			ScopeSpans: []otlpScopeSpan{{
				Scope: otlpScope{
					Name:    "ark.reliability",
					Version: Version,
				},
				Spans: []otlpSpan{{
					TraceID:           traceID,
					SpanID:            spanID,
					Name:              string(e.EventType),
					Kind:              1, // INTERNAL
					StartTimeUnixNano: strconv.FormatInt(e.TimestampNs, 10),
					EndTimeUnixNano:   strconv.FormatInt(endNs, 10),
					Status: otlpStatus{
						Code:    severityCode,
						Message: errMsg,
					},
					Attributes: attrs,
				}},
			}},
		}},
	}
}

func toOTLPValue(v interface{}) otlpValue {
	switch val := v.(type) {
	case bool:
		return otlpValue{BoolValue: &val}
	case int:
		s := strconv.Itoa(val)
		return otlpValue{IntValue: &s}
	case int64:
		s := strconv.FormatInt(val, 10)
		return otlpValue{IntValue: &s}
	case float64:
		return otlpValue{DoubleValue: &val}
	case string:
		return otlpValue{StringValue: &val}
	case []string:
		arr := make([]otlpValue, len(val))
		for i, sv := range val {
			s := sv
			arr[i] = otlpValue{StringValue: &s}
		}
		return otlpValue{ArrayValue: &otlpArray{Values: arr}}
	default:
		s := fmt.Sprintf("%v", v)
		return otlpValue{StringValue: &s}
	}
}

func strPtr(s string) *string { return &s }

// OTelExporterStats holds exporter statistics.
type OTelExporterStats struct {
	Enabled       bool   `json:"enabled"`
	Endpoint      string `json:"endpoint"`
	Buffered      int    `json:"buffered"`
	TotalEmitted  int64  `json:"total_emitted"`
	TotalDropped  int64  `json:"total_dropped"`
	ServiceName   string `json:"service_name"`
}

// OTelExporter emits ARK reliability events to an OTel Collector via OTLP/JSON.
type OTelExporter struct {
	mu            sync.Mutex
	endpoint      string
	serviceName   string
	batchSize     int
	flushInterval time.Duration
	enabled       bool
	httpClient    *http.Client

	buffer       *buffer.RingBuffer[*ReliabilityEvent]
	totalEmitted int64
	totalDropped int64
	lastFlush    time.Time
}

// NewOTelExporter creates a new OTelExporter.
// If endpoint is empty, it reads ARK_OTEL_ENDPOINT from the environment.
func NewOTelExporter(opts ...OTelExporterOption) *OTelExporter {
	e := &OTelExporter{
		endpoint:      os.Getenv("ARK_OTEL_ENDPOINT"),
		serviceName:   "ark",
		batchSize:     100,
		flushInterval: 5 * time.Second,
		httpClient:    &http.Client{Timeout: 2 * time.Second},
		lastFlush:     time.Now(),
	}

	for _, opt := range opts {
		opt(e)
	}

	e.enabled = e.endpoint != ""
	e.buffer = buffer.New[*ReliabilityEvent](e.batchSize)

	return e
}

// OTelExporterOption is a functional option for OTelExporter.
type OTelExporterOption func(*OTelExporter)

// WithOTelEndpoint sets the OTel Collector endpoint.
func WithOTelEndpoint(endpoint string) OTelExporterOption {
	return func(e *OTelExporter) { e.endpoint = endpoint }
}

// WithOTelServiceName sets the service name in OTLP payloads.
func WithOTelServiceName(name string) OTelExporterOption {
	return func(e *OTelExporter) { e.serviceName = name }
}

// WithOTelBatchSize sets the max batch size before auto-flush.
func WithOTelBatchSize(n int) OTelExporterOption {
	return func(e *OTelExporter) { e.batchSize = n }
}

// WithOTelFlushInterval sets the auto-flush interval.
func WithOTelFlushInterval(d time.Duration) OTelExporterOption {
	return func(e *OTelExporter) { e.flushInterval = d }
}

// Emit sends a reliability event.
func (e *OTelExporter) Emit(
	eventType ArkEventType,
	toolName string,
	traceID string,
	spanID string,
	attributes map[string]string,
	durationMs *float64,
	err *string,
) *ReliabilityEvent {
	if !e.enabled {
		e.mu.Lock()
		e.totalDropped++
		e.mu.Unlock()
		return nil
	}

	if traceID == "" {
		traceID = randomHex(32)
	}
	if spanID == "" {
		spanID = randomHex(16)
	}

	event := &ReliabilityEvent{
		EventType:   eventType,
		TimestampNs: time.Now().UnixNano(),
		TraceID:     traceID,
		SpanID:      spanID,
		ToolName:    toolName,
		Attributes:  attributes,
		DurationMs:  durationMs,
		Error:       err,
	}

	if attributes == nil {
		event.Attributes = make(map[string]string)
	}

	full := e.buffer.Push(event)

	e.mu.Lock()
	e.totalEmitted++
	shouldFlush := full || time.Since(e.lastFlush) >= e.flushInterval
	e.mu.Unlock()

	if shouldFlush {
		e.Flush()
	}

	return event
}

// Flush sends all buffered events to the OTel Collector.
func (e *OTelExporter) Flush() int {
	if !e.enabled {
		return 0
	}

	events := e.buffer.Drain()
	if len(events) == 0 {
		e.mu.Lock()
		e.lastFlush = time.Now()
		e.mu.Unlock()
		return 0
	}

	e.mu.Lock()
	e.lastFlush = time.Now()
	e.mu.Unlock()

	success := 0
	for _, event := range events {
		payload := event.ToOTLP(e.serviceName)
		data, err := json.Marshal(payload)
		if err != nil {
			e.mu.Lock()
			e.totalDropped++
			e.mu.Unlock()
			continue
		}

		req, err := http.NewRequest("POST", e.endpoint, bytes.NewReader(data))
		if err != nil {
			e.mu.Lock()
			e.totalDropped++
			e.mu.Unlock()
			continue
		}
		req.Header.Set("Content-Type", "application/json")

		resp, err := e.httpClient.Do(req)
		if err != nil {
			e.mu.Lock()
			e.totalDropped++
			e.mu.Unlock()
			continue
		}
		io.Copy(io.Discard, resp.Body)
		resp.Body.Close()
		if resp.StatusCode < 400 {
			success++
		} else {
			e.mu.Lock()
			e.totalDropped++
			e.mu.Unlock()
		}
	}

	return success
}

// Stats returns exporter statistics.
func (e *OTelExporter) Stats() OTelExporterStats {
	e.mu.Lock()
	defer e.mu.Unlock()
	endpoint := e.endpoint
	if endpoint == "" {
		endpoint = "(not configured)"
	}
	if !e.enabled && e.endpoint == "" {
		endpoint = "(disabled)"
	}
	return OTelExporterStats{
		Enabled:      e.enabled,
		Endpoint:     endpoint,
		Buffered:     e.buffer.Len(),
		TotalEmitted: e.totalEmitted,
		TotalDropped: e.totalDropped,
		ServiceName:  e.serviceName,
	}
}

// IsEnabled returns whether the exporter is active.
func (e *OTelExporter) IsEnabled() bool { return e.enabled }

// ---------------------------------------------------------------------------
// Global singleton
// ---------------------------------------------------------------------------

var (
	globalExporter *OTelExporter
	globalLock     sync.Mutex
)

// GetOTelExporter returns the global OTelExporter singleton.
func GetOTelExporter(opts ...OTelExporterOption) *OTelExporter {
	globalLock.Lock()
	defer globalLock.Unlock()
	if globalExporter == nil {
		globalExporter = NewOTelExporter(opts...)
	}
	return globalExporter
}

// ResetOTelExporter resets the global exporter (for tests).
func ResetOTelExporter() {
	globalLock.Lock()
	defer globalLock.Unlock()
	globalExporter = nil
}

// randomHex generates a hex string of the requested length using time+nanoseconds.
// NOT cryptographically secure; sufficient for trace/span IDs in demos.
func randomHex(n int) string {
	now := time.Now().UnixNano()
	var buf strings.Builder
	buf.Grow(n)
	for i := 0; i < n; i++ {
		// simple hash mixing
		h := byte(now>>(i%60)) ^ byte(now>>(i%60+1))
		buf.WriteByte("0123456789abcdef"[h&0xf])
	}
	return buf.String()
}
