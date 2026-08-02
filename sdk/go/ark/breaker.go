package ark

import (
	"context"
	"sync"
	"time"

	"github.com/wzg0911/ark-go/internal/clock"
)

// BreakerOption is a functional option for CircuitBreaker.
type BreakerOption func(*CircuitBreaker)

// WithBreakerThreshold sets the failure count before opening.
func WithBreakerThreshold(n int) BreakerOption {
	return func(b *CircuitBreaker) { b.threshold = n }
}

// WithBreakerRecoveryTime sets the time before transitioning to half-open.
func WithBreakerRecoveryTime(d time.Duration) BreakerOption {
	return func(b *CircuitBreaker) { b.recoveryTime = d }
}

// WithBreakerHalfOpenMax sets the max trials in half-open state.
func WithBreakerHalfOpenMax(n int) BreakerOption {
	return func(b *CircuitBreaker) { b.halfOpenMax = n }
}

// WithBreakerClock injects a clock for testing.
func WithBreakerClock(c clock.Clock) BreakerOption {
	return func(b *CircuitBreaker) { b.clock = c }
}

// WithBreakerEventCallback sets a callback for state change and event emissions.
func WithBreakerEventCallback(fn func(ArkEvent)) BreakerOption {
	return func(b *CircuitBreaker) { b.onEvent = fn }
}

// WithBreakerStateChangeCallback sets a callback for state changes.
func WithBreakerStateChangeCallback(fn func(from, to CircuitState)) BreakerOption {
	return func(b *CircuitBreaker) { b.onStateChange = fn }
}

// BreakerStats tracks CircuitBreaker metrics.
type BreakerStats struct {
	State        CircuitState `json:"state"`
	Failures     int          `json:"failures"`
	Successes    int          `json:"successes"`
	OpenCount    int64        `json:"open_count"`
	RejectCount  int64        `json:"reject_count"`
	LastFailure  time.Time    `json:"last_failure,omitempty"`
}

// CircuitBreaker implements the circuit breaker pattern.
// Three states: CLOSED (normal), OPEN (rejecting), HALF_OPEN (testing).
type CircuitBreaker struct {
	mu            sync.RWMutex
	state         CircuitState
	failureCount  int
	successCount  int
	threshold     int
	recoveryTime  time.Duration
	halfOpenMax   int
	lastFailure   time.Time
	clock         clock.Clock
	stats         BreakerStats
	onStateChange func(from, to CircuitState)
	onEvent       func(ArkEvent)
}

// NewCircuitBreaker creates a new breaker with sensible defaults.
func NewCircuitBreaker(opts ...BreakerOption) *CircuitBreaker {
	b := &CircuitBreaker{
		state:        CircuitClosed,
		threshold:    5,
		recoveryTime: 30 * time.Second,
		halfOpenMax:  3,
		clock:        clock.RealClock{},
	}
	for _, opt := range opts {
		opt(b)
	}
	return b
}

// Execute runs fn through the breaker. Returns ErrCircuitOpen if the breaker
// is open and the call is rejected.
func (b *CircuitBreaker) Execute(ctx context.Context, fn func(context.Context) error) error {
	// Check if we should reject
	b.mu.Lock()
	if b.state == CircuitOpen {
		if b.clock.Since(b.lastFailure) >= b.recoveryTime {
			b.transitionToLocked(CircuitHalfOpen)
		} else {
			b.stats.RejectCount++
			b.mu.Unlock()
			b.emit("ark.circuit.reject", "")
			return ErrCircuitOpen
		}
	}
	b.mu.Unlock()

	err := fn(ctx)

	b.mu.Lock()
	defer b.mu.Unlock()

	if err != nil {
		return b.recordFailureLocked(err)
	}

	return b.recordSuccessLocked()
}

func (b *CircuitBreaker) recordFailureLocked(err error) error {
	b.failureCount++
	b.stats.Failures++
	b.lastFailure = b.clock.Now()

	switch b.state {
	case CircuitClosed:
		if b.failureCount >= b.threshold {
			b.transitionToLocked(CircuitOpen)
			b.emit("ark.circuit.open", "")
		}
	case CircuitHalfOpen:
		b.transitionToLocked(CircuitOpen)
		b.emit("ark.circuit.open", "")
	}
	return err
}

func (b *CircuitBreaker) recordSuccessLocked() error {
	b.stats.Successes++

	switch b.state {
	case CircuitHalfOpen:
		b.successCount++
		if b.successCount >= b.halfOpenMax {
			b.transitionToLocked(CircuitClosed)
			b.failureCount = 0
			b.successCount = 0
			b.emit("ark.circuit.close", "")
		}
	case CircuitClosed:
		b.failureCount = 0 // reset on success
	}
	return nil
}

func (b *CircuitBreaker) transitionToLocked(to CircuitState) {
	from := b.state
	b.state = to
	b.stats.State = to
	if to == CircuitOpen {
		b.stats.OpenCount++
	}
	if b.onStateChange != nil {
		b.onStateChange(from, to)
	}
}

// State returns the current breaker state.
func (b *CircuitBreaker) State() CircuitState {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return b.state
}

// Stats returns a snapshot of breaker statistics.
func (b *CircuitBreaker) Stats() BreakerStats {
	b.mu.RLock()
	defer b.mu.RUnlock()
	s := b.stats
	s.State = b.state
	return s
}

// Reset returns the breaker to closed state and clears stats.
func (b *CircuitBreaker) Reset() {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.state = CircuitClosed
	b.failureCount = 0
	b.successCount = 0
	b.lastFailure = time.Time{}
	b.stats = BreakerStats{}
}

func (b *CircuitBreaker) emit(eventType, detail string) {
	if b.onEvent == nil {
		return
	}
	b.onEvent(ArkEvent{
		Type:      eventType,
		Timestamp: b.clock.Now(),
		Attrs: map[string]string{
			"detail": detail,
		},
	})
}
