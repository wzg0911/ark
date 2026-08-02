# ARK Go SDK Architecture Design (v0.7.0)

> **Status:** Draft — 2026-06-27
> **Target:** Multi-language SDK parity with Python core v0.6.0

---

## 1. Design Philosophy

### Parity-First
Go SDK mirrors the Python core module-by-module. Same API surface, same behavior, Go-idiomatic implementation.

### Zero External Dependencies (MVP)
Core modules (`guard`, `breaker`, `validator`) use only the Go standard library. OTel export uses `net/http` for OTLP/JSON — no SDK dependency.

### Interface-Driven
Every component exposes an interface, enabling mock-based testing and custom implementations.

### Concurrency-Safe
All stateful components (breaker, guard cache) use `sync.RWMutex`. Safe for concurrent goroutines.

---

## 2. Package Structure

```
sdk/go/
├── go.mod                    # module github.com/wzg0911/ark-go
├── go.sum
├── README.md
├── ark/
│   ├── ark.go                # Package doc + version constant
│   ├── types.go              # Core types (ArkEvent, CircuitState, ValidationResult)
│   ├── guard.go              # IdempotencyGuard
│   ├── guard_test.go
│   ├── breaker.go            # CircuitBreaker
│   ├── breaker_test.go
│   ├── validator.go          # OutputValidator
│   ├── validator_test.go
│   ├── otel.go               # OTelExporter (batch buffer + OTLP/JSON HTTP export)
│   ├── otel_test.go
│   ├── score.go              # ReliabilityScore
│   ├── score_test.go
│   ├── trace.go              # Trace / Span (optional phase 2)
│   └── errors.go             # Error types
├── examples/
│   └── basic/
│       └── main.go           # End-to-end usage example
└── internal/
    ├── buffer/               # Ring buffer for OTel batching
    │   └── ring.go
    └── clock/                # Clock interface for testable time
        └── clock.go
```

---

## 3. Core Types (`types.go`)

```go
package ark

// CircuitState represents breaker state machine.
type CircuitState int

const (
    CircuitClosed    CircuitState = iota // normal operation
    CircuitOpen                          // failing, rejecting calls
    CircuitHalfOpen                      // testing recovery
)

// ArkEvent represents a reliability event emitted by ARK components.
type ArkEvent struct {
    Type      string            // e.g. "ark.idempotency.hit"
    Timestamp time.Time
    AgentID   string
    TraceID   string
    SpanID    string
    Attrs     map[string]string
}

// ValidationResult from OutputValidator.
type ValidationResult struct {
    Passed  bool
    Errors  []ValidationError
    Warnings []string
}

type ValidationError struct {
    Field   string
    Message string
    Value   interface{}
}

// Version is the current SDK version.
const Version = "0.7.0"
```

---

## 4. Component Designs

### 4.1 IdempotencyGuard (`guard.go`)

```go
type IdempotencyGuard struct {
    mu     sync.RWMutex
    cache  map[string]idempotencyEntry
    ttl    time.Duration
    maxSize int
    clock  clock.Clock
    stats  GuardStats
    onEvent func(ArkEvent)
}

type idempotencyEntry struct {
    result    interface{}
    timestamp time.Time
}

// Constructor
func NewIdempotencyGuard(opts ...GuardOption) *IdempotencyGuard

// CheckOrExecute: if key seen within TTL, return cached; else execute fn.
func (g *IdempotencyGuard) CheckOrExecute(
    ctx context.Context,
    key string,
    fn func(context.Context) (interface{}, error),
) (interface{}, bool, error)
// Returns: (result, wasDuplicate, error)

// Functional options pattern
type GuardOption func(*IdempotencyGuard)
func WithGuardTTL(d time.Duration) GuardOption
func WithGuardMaxSize(n int) GuardOption
func WithGuardEventCallback(fn func(ArkEvent)) GuardOption
```

**Behavior:** Matches Python `IdempotencyGuard` exactly:
- Key hash → cache check → return cached if within TTL (emits `ark.idempotency.hit`)
- Otherwise execute fn → cache result → return (emits `ark.idempotency.miss`)
- Background TTL cleanup goroutine (ticker-based)
- LRU eviction when maxSize exceeded

### 4.2 CircuitBreaker (`breaker.go`)

```go
type CircuitBreaker struct {
    mu            sync.RWMutex
    state         CircuitState
    failureCount  int
    successCount  int
    threshold     int           // failures before opening
    recoveryTime  time.Duration // time before half-open
    halfOpenMax   int           // max trials in half-open
    lastFailure   time.Time
    clock         clock.Clock
    stats         BreakerStats
    onStateChange func(from, to CircuitState)
    onEvent       func(ArkEvent)
}

// Execute runs fn through the breaker.
func (b *CircuitBreaker) Execute(
    ctx context.Context,
    fn func(context.Context) error,
) error

// Functional options
func WithBreakerThreshold(n int) BreakerOption
func WithBreakerRecoveryTime(d time.Duration) BreakerOption
func WithBreakerHalfOpenMax(n int) BreakerOption
```

**State machine:**
- CLOSED → failures ≥ threshold → OPEN (emit `ark.circuit.open`)
- OPEN → recoveryTime elapsed → HALF_OPEN
- HALF_OPEN → any failure → OPEN; successCount ≥ halfOpenMax → CLOSED (emit `ark.circuit.close`)

### 4.3 OutputValidator (`validator.go`)

```go
type OutputValidator struct {
    schemas map[string]ValidationSchema
    mu      sync.RWMutex
    stats   ValidatorStats
    onEvent func(ArkEvent)
}

type ValidationSchema struct {
    Fields []FieldRule
}

type FieldRule struct {
    Name     string
    Type     string        // "string", "number", "bool", "array", "object"
    Required bool
    Min      *float64
    Max      *float64
    Pattern  string        // regex
    MinLen   *int
    MaxLen   *int
    Enum     []interface{}
    Children []FieldRule   // for nested objects
}

// Validate checks output against schema.
func (v *OutputValidator) Validate(
    schemaName string,
    data map[string]interface{},
) ValidationResult

// RegisterSchema adds a validation schema.
func (v *OutputValidator) RegisterSchema(name string, schema ValidationSchema)

// Quick helpers
func NewNumberRule(name string, min, max float64) FieldRule
func NewStringRule(name string, pattern string) FieldRule
func NewRequiredRule(name string) FieldRule
```

### 4.4 OTelExporter (`otel.go`)

```go
type OTelExporter struct {
    endpoint   string
    buffer     *buffer.RingBuffer[ArkEvent]
    client     *http.Client
    batchSize  int
    flushEvery time.Duration
    stopCh     chan struct{}
    stats      OTelStats
    mu         sync.Mutex
}

// Endpoint set via ARK_OTEL_ENDPOINT env var or explicit option.
func NewOTelExporter(opts ...OTelOption) *OTelExporter

// Start begins the background flush timer.
func (e *OTelExporter) Start(ctx context.Context)

// Emit adds event to buffer. Auto-flushes when batch full.
func (e *OTelExporter) Emit(event ArkEvent)

// Flush sends all buffered events to OTLP endpoint.
func (e *OTelExporter) Flush(ctx context.Context) error

// Stop shuts down the exporter gracefully.
func (e *OTelExporter) Stop() error

// Functional options
func WithOTelEndpoint(url string) OTelOption
func WithOTelBatchSize(n int) OTelOption
func WithOTelFlushInterval(d time.Duration) OTelOption
```

**Zero-overhead when disabled:** `ARK_OTEL_ENDPOINT` env var not set → exporter is nil → no allocations.

---

## 5. Error Types (`errors.go`)

```go
var (
    ErrCircuitOpen    = errors.New("ark: circuit breaker is open")
    ErrValidationFail = errors.New("ark: output validation failed")
)

type ValidationFailedError struct {
    Result ValidationResult
}
func (e *ValidationFailedError) Error() string
```

---

## 6. Go Module Definition

```
module github.com/wzg0911/ark-go

go 1.21

// Zero external dependencies for MVP
// Future: otel sdk bridge (optional, behind build tag)
```

---

## 7. Testing Strategy

| Test Type | Framework | Target |
|-----------|-----------|--------|
| Unit tests | `testing` (stdlib) | 100% of core logic |
| Race detection | `go test -race` | All concurrent code |
| Table-driven | `testing` | Parameterized behavior |
| Benchmarks | `testing.B` | Perf regression guard |

### Test Coverage Targets
- `guard_test.go`: 12+ cases (cache hit/miss, TTL expiry, max size eviction, concurrent access)
- `breaker_test.go`: 15+ cases (open/close/half-open transitions, recovery timeout, concurrent calls)
- `validator_test.go`: 10+ cases (pass/fail, type mismatch, boundary, regex, nested schemas)
- `otel_test.go`: 10+ cases (emit, flush, batch full, network error, disabled mode)

---

## 8. CI Integration

```yaml
# .github/workflows/go-sdk.yml
name: Go SDK
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        go: ['1.21', '1.22', '1.23']
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version: ${{ matrix.go }}
      - run: cd sdk/go && go test -race -cover ./...
      - run: cd sdk/go && go vet ./...
```

---

## 9. Release Plan

| Milestone | Scope | Timeline |
|-----------|-------|----------|
| **v0.7.0-alpha** | guard + breaker + validator + types | 2-3 days |
| **v0.7.0-beta** | otel exporter + score + tests 30+ | 2-3 days |
| **v0.7.0** | full test suite (50+), examples, CI, README | 2-3 days |
| **v0.7.1** | Go module published | +1 day |

---

## 10. Cross-SDK Parity Matrix

| Module | Python v0.6.0 | TypeScript v0.6.0 | Go v0.7.0 |
|--------|:---:|:---:|:---:|
| IdempotencyGuard | ✅ | ✅ | 🎯 |
| CircuitBreaker | ✅ | ✅ | 🎯 |
| OutputValidator | ✅ | ✅ | 🎯 |
| OTelExporter | ✅ | ✅ | 🎯 |
| ReliabilityScore | ✅ | ❌ | 🎯 |
| Trace | ✅ | ❌ | ⏳ P2 |
| StatefulBreaker | ✅ | ❌ | ⏳ P2 |
| MultiAgent | ✅ | ❌ | ⏳ P3 |
| Dashboard | ✅ | ❌ | ⏳ P3 |
| ProactiveGuard | ✅ | ❌ | ⏳ P3 |

---

*Design by ARK 7×24 Cruise — 2026-06-27 20:09 CST*
