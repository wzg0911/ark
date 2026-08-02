package ark

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/wzg0911/ark-go/internal/clock"
)

func TestBreakerOpensAfterFailures(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(3))

	for i := 0; i < 3; i++ {
		err := b.Execute(context.Background(), func(ctx context.Context) error {
			return errors.New("fail")
		})
		if err == nil {
			t.Fatal("expected error from fn")
		}
	}

	if b.State() != CircuitOpen {
		t.Fatalf("expected OPEN, got %s", b.State())
	}
}

func TestBreakerRejectsWhenOpen(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(2))

	// Open the breaker
	for i := 0; i < 2; i++ {
		_ = b.Execute(context.Background(), func(ctx context.Context) error {
			return errors.New("fail")
		})
	}

	if b.State() != CircuitOpen {
		t.Fatal("breaker should be open")
	}

	err := b.Execute(context.Background(), func(ctx context.Context) error {
		t.Fatal("should not be called when breaker is open")
		return nil
	})

	if !errors.Is(err, ErrCircuitOpen) {
		t.Fatalf("expected ErrCircuitOpen, got %v", err)
	}

	s := b.Stats()
	if s.RejectCount != 1 {
		t.Fatalf("expected 1 reject, got %d", s.RejectCount)
	}
}

func TestBreakerHalfOpenRecovery(t *testing.T) {
	fixed := &clock.FixedClock{T: time.Now()}
	b := NewCircuitBreaker(
		WithBreakerThreshold(2),
		WithBreakerRecoveryTime(10*time.Second),
		WithBreakerHalfOpenMax(2),
		WithBreakerClock(fixed),
	)

	// Open the breaker
	for i := 0; i < 2; i++ {
		_ = b.Execute(context.Background(), func(ctx context.Context) error {
			return errors.New("fail")
		})
	}
	if b.State() != CircuitOpen {
		t.Fatal("expected OPEN")
	}

	// Advance past recovery time
	fixed.T = fixed.T.Add(15 * time.Second)

	// First call after timeout → half-open, succeeds
	err := b.Execute(context.Background(), func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if b.State() != CircuitHalfOpen {
		t.Fatalf("expected HALF_OPEN, got %s", b.State())
	}

	// Second success closes it
	err = b.Execute(context.Background(), func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if b.State() != CircuitClosed {
		t.Fatalf("expected CLOSED after recovery, got %s", b.State())
	}
}

func TestBreakerHalfOpenFailsBack(t *testing.T) {
	fixed := &clock.FixedClock{T: time.Now()}
	b := NewCircuitBreaker(
		WithBreakerThreshold(2),
		WithBreakerRecoveryTime(10*time.Second),
		WithBreakerClock(fixed),
	)

	// Open
	for i := 0; i < 2; i++ {
		_ = b.Execute(context.Background(), func(ctx context.Context) error {
			return errors.New("fail")
		})
	}

	// Advance → half-open
	fixed.T = fixed.T.Add(15 * time.Second)

	// Fails in half-open → back to open
	err := b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("half-open fail")
	})
	if err == nil {
		t.Fatal("expected error")
	}
	if b.State() != CircuitOpen {
		t.Fatalf("expected back to OPEN, got %s", b.State())
	}
}

func TestBreakerReset(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(2))

	// Open it
	for i := 0; i < 2; i++ {
		_ = b.Execute(context.Background(), func(ctx context.Context) error {
			return errors.New("fail")
		})
	}
	if b.State() != CircuitOpen {
		t.Fatal("expected OPEN before reset")
	}

	b.Reset()
	if b.State() != CircuitClosed {
		t.Fatalf("expected CLOSED after reset, got %s", b.State())
	}

	s := b.Stats()
	if s.Failures != 0 || s.Successes != 0 || s.OpenCount != 0 || s.RejectCount != 0 {
		t.Fatal("stats not cleared after reset")
	}

	// Should work normally after reset
	err := b.Execute(context.Background(), func(ctx context.Context) error {
		return nil
	})
	if err != nil {
		t.Fatalf("unexpected error after reset: %v", err)
	}
}

func TestBreakerStats(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(3))

	// 2 failures, 1 success
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("f1")
	})
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return nil
	})
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("f2")
	})

	s := b.Stats()
	if s.Failures != 2 {
		t.Fatalf("expected 2 failures, got %d", s.Failures)
	}
	if s.Successes != 1 {
		t.Fatalf("expected 1 success, got %d", s.Successes)
	}
	if s.State != CircuitClosed {
		t.Fatalf("expected CLOSED, got %s", s.State)
	}
}

func TestBreakerStateChangeCallback(t *testing.T) {
	var transitions []struct{ from, to CircuitState }
	mu := sync.Mutex{}

	b := NewCircuitBreaker(
		WithBreakerThreshold(1),
		WithBreakerStateChangeCallback(func(from, to CircuitState) {
			mu.Lock()
			transitions = append(transitions, struct{ from, to CircuitState }{from, to})
			mu.Unlock()
		}),
	)

	// Fail to open
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("fail")
	})

	mu.Lock()
	if len(transitions) != 1 {
		t.Fatalf("expected 1 transition, got %d", len(transitions))
	}
	if transitions[0].from != CircuitClosed || transitions[0].to != CircuitOpen {
		t.Fatalf("expected Closed→Open, got %s→%s", transitions[0].from, transitions[0].to)
	}
	mu.Unlock()
}

func TestBreakerEventEmission(t *testing.T) {
	var events []ArkEvent
	mu := sync.Mutex{}

	b := NewCircuitBreaker(
		WithBreakerThreshold(1),
		WithBreakerEventCallback(func(e ArkEvent) {
			mu.Lock()
			events = append(events, e)
			mu.Unlock()
		}),
	)

	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("fail")
	})

	mu.Lock()
	if len(events) < 1 {
		t.Fatal("expected at least 1 event")
	}
	if events[0].Type != "ark.circuit.open" {
		t.Fatalf("expected ark.circuit.open, got %s", events[0].Type)
	}
	mu.Unlock()
}

func TestBreakerNeverOpenForSuccess(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(3))

	for i := 0; i < 100; i++ {
		err := b.Execute(context.Background(), func(ctx context.Context) error {
			return nil
		})
		if err != nil {
			t.Fatalf("unexpected error on iteration %d: %v", i, err)
		}
	}
	if b.State() != CircuitClosed {
		t.Fatal("should stay CLOSED with only successes")
	}
}

func TestBreakerConcurrentAccess(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(10))
	var wg sync.WaitGroup
	errorsCount := 0
	var mu sync.Mutex

	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			err := b.Execute(context.Background(), func(ctx context.Context) error {
				return nil
			})
			if err != nil {
				mu.Lock()
				errorsCount++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()

	if errorsCount > 0 {
		t.Fatalf("expected 0 errors, got %d", errorsCount)
	}
	if b.State() != CircuitClosed {
		t.Fatal("should stay CLOSED")
	}
}

func TestBreakerZeroThreshold(t *testing.T) {
	// Zero threshold: opens on first failure
	b := NewCircuitBreaker(WithBreakerThreshold(0))

	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("fail")
	})

	if b.State() != CircuitOpen {
		t.Fatalf("expected OPEN with zero threshold, got %s", b.State())
	}
}

func TestBreakerFallbackOnError(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(2))

	// Open it
	for i := 0; i < 2; i++ {
		_ = b.Execute(context.Background(), func(ctx context.Context) error {
			return errors.New("fail")
		})
	}

	// Verify subsequent calls return ErrCircuitOpen
	for i := 0; i < 5; i++ {
		err := b.Execute(context.Background(), func(ctx context.Context) error {
			return nil
		})
		if !errors.Is(err, ErrCircuitOpen) {
			t.Fatalf("iteration %d: expected ErrCircuitOpen, got %v", i, err)
		}
	}

	if b.Stats().RejectCount != 5 {
		t.Fatalf("expected 5 rejects, got %d", b.Stats().RejectCount)
	}
}

func TestBreakerOpenCountIncrement(t *testing.T) {
	b := NewCircuitBreaker(
		WithBreakerThreshold(1),
		WithBreakerRecoveryTime(1*time.Millisecond),
	)

	// Open once
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("fail")
	})
	if b.Stats().OpenCount != 1 {
		t.Fatalf("expected OpenCount=1, got %d", b.Stats().OpenCount)
	}

	// Wait and fail again in half-open
	time.Sleep(2 * time.Millisecond)
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("fail again")
	})

	if b.Stats().OpenCount != 2 {
		t.Fatalf("expected OpenCount=2, got %d", b.Stats().OpenCount)
	}
}

func TestBreakerStatsSnapshot(t *testing.T) {
	b := NewCircuitBreaker(WithBreakerThreshold(2))
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return errors.New("f")
	})
	_ = b.Execute(context.Background(), func(ctx context.Context) error {
		return nil
	})

	s1 := b.Stats()
	s2 := b.Stats()
	if s1.State != s2.State {
		t.Fatal("stats snapshots should be consistent")
	}
}
