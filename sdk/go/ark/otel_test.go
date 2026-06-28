package ark

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestEventTypes_Unique(t *testing.T) {
	all := AllEventTypes()
	if len(all) != 8 {
		t.Fatalf("expected 8 event types, got %d", len(all))
	}
	seen := make(map[string]bool)
	for _, et := range all {
		if seen[string(et)] {
			t.Fatalf("duplicate event type: %s", et)
		}
		seen[string(et)] = true
	}
}

func TestOTLPConversion_Basic(t *testing.T) {
	now := time.Now().UnixNano()
	errMsg := "test error"
	event := &ReliabilityEvent{
		EventType:   EventValidationFail,
		TimestampNs: now,
		TraceID:     "abc123",
		SpanID:      "def456",
		ToolName:    "test_tool",
		Attributes: map[string]string{
			"key": "value",
		},
		Error: &errMsg,
	}

	payload := event.ToOTLP("ark-test")
	if len(payload.ResourceSpans) != 1 {
		t.Fatal("expected 1 resourceSpan")
	}
	rs := payload.ResourceSpans[0]

	// Check resource attributes
	hasService := false
	for _, attr := range rs.Resource.Attributes {
		if attr.Key == "service.name" && attr.Value.StringValue != nil && *attr.Value.StringValue == "ark-test" {
			hasService = true
		}
	}
	if !hasService {
		t.Error("missing service.name attribute")
	}

	// Check scope spans
	if len(rs.ScopeSpans) != 1 {
		t.Fatal("expected 1 scopeSpan")
	}
	ss := rs.ScopeSpans[0]
	if len(ss.Spans) != 1 {
		t.Fatal("expected 1 span")
	}
	span := ss.Spans[0]

	if span.Name != string(EventValidationFail) {
		t.Errorf("expected span name %q, got %q", EventValidationFail, span.Name)
	}
	if span.Kind != 1 {
		t.Errorf("expected INTERNAL kind (1), got %d", span.Kind)
	}
	if span.Status.Code != 2 {
		t.Errorf("expected ERROR status (2), got %d", span.Status.Code)
	}

	// Check padded IDs (32-char trace, 16-char span)
	if len(span.TraceID) != 32 {
		t.Errorf("trace ID should be 32 chars, got %d: %s", len(span.TraceID), span.TraceID)
	}
	if len(span.SpanID) != 16 {
		t.Errorf("span ID should be 16 chars, got %d: %s", len(span.SpanID), span.SpanID)
	}

	// Check attributes (tool_name + event_type + custom)
	if len(span.Attributes) < 3 {
		t.Fatalf("expected at least 3 attributes, got %d", len(span.Attributes))
	}
}

func TestOTLPConversion_NoError(t *testing.T) {
	event := &ReliabilityEvent{
		EventType:   EventValidationPass,
		TimestampNs: time.Now().UnixNano(),
		TraceID:     "t1",
		SpanID:      "s1",
		ToolName:    "ok",
	}
	payload := event.ToOTLP("ark")
	span := payload.ResourceSpans[0].ScopeSpans[0].Spans[0]
	if span.Status.Code != 1 {
		t.Errorf("expected OK status (1), got %d", span.Status.Code)
	}
}

func TestOTLPConversion_Duration(t *testing.T) {
	dur := 150.0
	event := &ReliabilityEvent{
		EventType:   EventIdempotencyHit,
		TimestampNs: 1000,
		TraceID:     "t",
		SpanID:      "s",
		ToolName:    "dur",
		DurationMs:  &dur,
	}
	payload := event.ToOTLP("ark")
	span := payload.ResourceSpans[0].ScopeSpans[0].Spans[0]
	endNs := span.EndTimeUnixNano
	// 1000 (start) + 150*1_000_000 (duration in ns) = 150_001_000
	if endNs != "150001000" {
		t.Errorf("expected endTime 150001000, got %s", endNs)
	}
}

func TestExporterDisabled_WithoutEndpoint(t *testing.T) {
	// Ensure env is not set
	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter()
	if e.IsEnabled() {
		t.Error("exporter should be disabled without endpoint")
	}

	evt := e.Emit(EventIdempotencyHit, "test", "", "", nil, nil, nil)
	if evt != nil {
		t.Error("emit should return nil when disabled")
	}

	stats := e.Stats()
	if stats.Enabled {
		t.Error("stats should show disabled")
	}
	if stats.TotalDropped != 1 {
		t.Errorf("expected 1 dropped, got %d", stats.TotalDropped)
	}
}

func TestExporter_ExplicitDisable(t *testing.T) {
	os.Setenv("ARK_OTEL_ENDPOINT", "http://localhost:4318")
	defer os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()

	e := NewOTelExporter()
	// Override endpoint to empty to simulate explicit disable
	e.endpoint = ""
	e.enabled = false

	if e.IsEnabled() {
		t.Error("explicitly disabled exporter should not be enabled")
	}
}

func TestExporter_EmitAndFlush(t *testing.T) {
	// Start a test HTTP server
	var receivedPayloads [][]byte
	var mu sync.Mutex
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		body, _ := ioReadAll(r.Body)
		receivedPayloads = append(receivedPayloads, body)
		w.WriteHeader(200)
	}))
	defer server.Close()

	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint(server.URL + "/v1/events"),
		WithOTelBatchSize(5),
	)

	if !e.IsEnabled() {
		t.Fatal("exporter should be enabled with endpoint")
	}

	// Emit 3 events (should not auto-flush at batch 5)
	for i := 0; i < 3; i++ {
		evt := e.Emit(EventIdempotencyHit, "tool_a", "trace1", "span1", nil, nil, nil)
		if evt == nil {
			t.Fatal("emit should return event")
		}
	}

	// Manual flush
	flushed := e.Flush()
	if flushed != 3 {
		t.Errorf("expected 3 flushed, got %d", flushed)
	}

	time.Sleep(100 * time.Millisecond)

	mu.Lock()
	n := len(receivedPayloads)
	mu.Unlock()
	if n != 3 {
		t.Errorf("expected 3 received payloads, got %d", n)
	}

	stats := e.Stats()
	if stats.TotalEmitted != 3 {
		t.Errorf("expected 3 emitted, got %d", stats.TotalEmitted)
	}
}

func TestExporter_AutoFlushOnFull(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
	}))
	defer server.Close()

	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint(server.URL),
		WithOTelBatchSize(3),
	)

	// Emit exactly 3 events → auto-flush on the 3rd
	for i := 0; i < 3; i++ {
		e.Emit(EventCircuitOpen, "breaker", "", "", nil, nil, nil)
	}

	stats := e.Stats()
	if stats.TotalEmitted != 3 {
		t.Errorf("expected 3 emitted, got %d", stats.TotalEmitted)
	}
	if stats.Buffered > 0 {
		t.Errorf("buffer should be empty after auto-flush, got %d buffered", stats.Buffered)
	}
}

func TestExporter_FlushClearsBuffer(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
	}))
	defer server.Close()

	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint(server.URL),
		WithOTelBatchSize(10),
	)

	e.Emit(EventValidationPass, "v", "", "", nil, nil, nil)
	e.Emit(EventValidationFail, "v", "", "", nil, nil, nil)

	if e.buffer.Len() != 2 {
		t.Errorf("expected 2 buffered, got %d", e.buffer.Len())
	}

	e.Flush()

	if e.buffer.Len() != 0 {
		t.Errorf("buffer should be empty after flush, got %d", e.buffer.Len())
	}
}

func TestExporter_FlushHandlesNetworkError(t *testing.T) {
	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint("http://127.0.0.1:19999/v1/events"), // non-existent
		WithOTelBatchSize(5),
	)

	e.Emit(EventGuardianIntercept, "g", "", "", nil, nil, nil)
	flushed := e.Flush()
	if flushed != 0 {
		t.Errorf("expected 0 flushed (network error), got %d", flushed)
	}

	stats := e.Stats()
	if stats.TotalDropped != 1 {
		t.Errorf("expected 1 dropped, got %d", stats.TotalDropped)
	}
}

func TestExporter_HTTPStatusErrors(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(500)
	}))
	defer server.Close()

	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint(server.URL),
		WithOTelBatchSize(3),
	)

	e.Emit(EventIdempotencyHit, "t", "", "", nil, nil, nil)
	e.Emit(EventIdempotencyMiss, "t", "", "", nil, nil, nil)
	flushed := e.Flush()
	if flushed != 0 {
		t.Errorf("expected 0 flushed (500 error), got %d", flushed)
	}

	stats := e.Stats()
	if stats.TotalDropped != 2 {
		t.Errorf("expected 2 dropped, got %d", stats.TotalDropped)
	}
}

func TestExporter_GlobalSingleton(t *testing.T) {
	os.Setenv("ARK_OTEL_ENDPOINT", "http://localhost:4318")
	defer os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()

	e1 := GetOTelExporter()
	e2 := GetOTelExporter()
	if e1 != e2 {
		t.Error("GetOTelExporter should return the same instance")
	}
}

func TestExporter_GlobalReset(t *testing.T) {
	os.Setenv("ARK_OTEL_ENDPOINT", "http://localhost:4318")
	defer os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()

	e1 := GetOTelExporter()
	ResetOTelExporter()
	e2 := GetOTelExporter()
	if e1 == e2 {
		t.Error("ResetOTelExporter should create a new instance")
	}
}

func TestExporter_Stats(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
	}))
	defer server.Close()

	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint(server.URL),
		WithOTelServiceName("ark-prod"),
		WithOTelBatchSize(10),
	)

	e.Emit(EventCircuitClose, "breaker", "", "", nil, nil, nil)
	e.Flush()

	stats := e.Stats()
	if !stats.Enabled {
		t.Error("stats should show enabled")
	}
	if stats.ServiceName != "ark-prod" {
		t.Errorf("expected service name ark-prod, got %s", stats.ServiceName)
	}
	if stats.TotalEmitted != 1 {
		t.Errorf("expected 1 emitted, got %d", stats.TotalEmitted)
	}
	if stats.TotalDropped != 0 {
		t.Errorf("expected 0 dropped, got %d", stats.TotalDropped)
	}
}

func TestExporter_FlushEmpty(t *testing.T) {
	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint("http://localhost:4318"),
	)

	flushed := e.Flush()
	if flushed != 0 {
		t.Errorf("expected 0 flushed for empty buffer, got %d", flushed)
	}
}

func TestExporter_FlushDisabled(t *testing.T) {
	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter() // no endpoint → disabled

	flushed := e.Flush()
	if flushed != 0 {
		t.Errorf("disabled exporter should flush 0, got %d", flushed)
	}
}

func TestExporter_ConcurrentEmit(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(200)
	}))
	defer server.Close()

	os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()
	e := NewOTelExporter(
		WithOTelEndpoint(server.URL),
		WithOTelBatchSize(50),
	)

	var wg sync.WaitGroup
	n := 20
	wg.Add(n)
	for i := 0; i < n; i++ {
		go func(idx int) {
			defer wg.Done()
			e.Emit(EventIdempotencyHit, "concurrent", "", "", nil, nil, nil)
		}(i)
	}
	wg.Wait()

	e.Flush()

	stats := e.Stats()
	if stats.TotalEmitted != int64(n) {
		t.Errorf("expected %d emitted, got %d", n, stats.TotalEmitted)
	}
}

func TestOTLPConversion_AllEventTypes(t *testing.T) {
	for _, et := range AllEventTypes() {
		event := &ReliabilityEvent{
			EventType:   et,
			TimestampNs: time.Now().UnixNano(),
			TraceID:     "t",
			SpanID:      "s",
			ToolName:    "test",
		}
		payload := event.ToOTLP("ark")
		span := payload.ResourceSpans[0].ScopeSpans[0].Spans[0]
		if span.Name != string(et) {
			t.Errorf("event type %s: span name mismatch: %s", et, span.Name)
		}

		// Serialize to ensure valid JSON
		data, err := json.Marshal(payload)
		if err != nil {
			t.Errorf("event type %s: json marshal failed: %v", et, err)
		}
		if len(data) == 0 {
			t.Errorf("event type %s: empty json", et)
		}
	}
}

func TestOTLPConversion_EmptyAttributes(t *testing.T) {
	event := &ReliabilityEvent{
		EventType:   EventGuardianIntercept,
		TimestampNs: time.Now().UnixNano(),
		TraceID:     "t",
		SpanID:      "s",
		ToolName:    "guard",
		Attributes:  nil,
	}
	// Should not panic
	payload := event.ToOTLP("ark")
	if payload == nil {
		t.Fatal("payload should not be nil")
	}
	data, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("json marshal failed: %v", err)
	}
	if len(data) == 0 {
		t.Fatal("empty json")
	}
}

func TestToOTLPValue_Types(t *testing.T) {
	tests := []struct {
		name  string
		input interface{}
	}{
		{"bool", true},
		{"int", 42},
		{"int64", int64(100)},
		{"float64", 3.14},
		{"string", "hello"},
		{"slice", []string{"a", "b"}},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			v := toOTLPValue(tt.input)
			data, err := json.Marshal(v)
			if err != nil {
				t.Errorf("marshal failed: %v", err)
			}
			if len(data) == 0 {
				t.Error("empty result")
			}
		})
	}
}

func TestExporter_EnvEndpoint(t *testing.T) {
	os.Setenv("ARK_OTEL_ENDPOINT", "http://otel:4318/v1/events")
	defer os.Unsetenv("ARK_OTEL_ENDPOINT")
	ResetOTelExporter()

	e := NewOTelExporter()
	if !e.IsEnabled() {
		t.Error("exporter should be enabled when ARK_OTEL_ENDPOINT is set")
	}
	if e.endpoint != "http://otel:4318/v1/events" {
		t.Errorf("endpoint mismatch: %s", e.endpoint)
	}
}

// ioReadAll reads all from a reader (go 1.16+ compatible helper)
func ioReadAll(r io.Reader) ([]byte, error) {
	b := new(strings.Builder)
	_, err := io.Copy(b, r)
	return []byte(b.String()), err
}
