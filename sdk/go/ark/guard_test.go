package ark

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/wzg0911/ark-go/internal/clock"
)

func TestGuardBasicDuplicate(t *testing.T) {
	g := NewIdempotencyGuard(WithGuardTTL(1 * time.Hour))

	callCount := 0
	fn := func(ctx context.Context) (interface{}, error) {
		callCount++
		return "result", nil
	}

	r1, dup1, err := g.CheckOrExecute(context.Background(), "key1", fn)
	if err != nil || dup1 || r1 != "result" {
		t.Fatalf("first call: result=%v dup=%v err=%v", r1, dup1, err)
	}
	if callCount != 1 {
		t.Fatalf("expected 1 call, got %d", callCount)
	}

	r2, dup2, err := g.CheckOrExecute(context.Background(), "key1", fn)
	if err != nil || !dup2 || r2 != "result" {
		t.Fatalf("second call: result=%v dup=%v err=%v", r2, dup2, err)
	}
	if callCount != 1 {
		t.Fatalf("expected still 1 call, got %d", callCount)
	}
}

func TestGuardDifferentKeys(t *testing.T) {
	g := NewIdempotencyGuard()

	callCount := 0
	fn := func(ctx context.Context) (interface{}, error) {
		callCount++
		return callCount, nil
	}

	r1, dup1, _ := g.CheckOrExecute(context.Background(), "a", fn)
	r2, dup2, _ := g.CheckOrExecute(context.Background(), "b", fn)
	r3, dup3, _ := g.CheckOrExecute(context.Background(), "c", fn)

	if dup1 || dup2 || dup3 {
		t.Fatal("different keys should not be duplicates")
	}
	if r1 != 1 || r2 != 2 || r3 != 3 {
		t.Fatalf("unexpected results: %v %v %v", r1, r2, r3)
	}
}

func TestGuardTTLExpiry(t *testing.T) {
	fixed := &clock.FixedClock{T: time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)}
	g := NewIdempotencyGuard(
		WithGuardTTL(1*time.Second),
		WithGuardClock(fixed),
	)

	callCount := 0
	fn := func(ctx context.Context) (interface{}, error) {
		callCount++
		return callCount, nil
	}

	// First call at T=0
	r1, dup1, _ := g.CheckOrExecute(context.Background(), "key", fn)
	if dup1 || r1 != 1 {
		t.Fatal("first call should not be duplicate")
	}

	// Advance clock past TTL
	fixed.T = fixed.T.Add(2 * time.Second)

	// Second call after TTL — should re-execute
	r2, dup2, _ := g.CheckOrExecute(context.Background(), "key", fn)
	if dup2 || r2 != 2 {
		t.Fatalf("after TTL should re-execute: dup=%v result=%v", dup2, r2)
	}
	if callCount != 2 {
		t.Fatalf("expected 2 calls, got %d", callCount)
	}
}

func TestGuardStats(t *testing.T) {
	g := NewIdempotencyGuard()

	fn := func(ctx context.Context) (interface{}, error) {
		return "ok", nil
	}

	g.CheckOrExecute(context.Background(), "k1", fn) // miss
	g.CheckOrExecute(context.Background(), "k1", fn) // hit
	g.CheckOrExecute(context.Background(), "k2", fn) // miss
	g.CheckOrExecute(context.Background(), "k2", fn) // hit
	g.CheckOrExecute(context.Background(), "k3", fn) // miss

	s := g.Stats()
	if s.Hits != 2 || s.Misses != 3 {
		t.Fatalf("stats: hits=%d misses=%d", s.Hits, s.Misses)
	}
	if s.CacheSize != 3 {
		t.Fatalf("cache_size=%d, want 3", s.CacheSize)
	}
}

func TestGuardMaxSizeEviction(t *testing.T) {
	g := NewIdempotencyGuard(WithGuardMaxSize(2))

	fn := func(ctx context.Context) (interface{}, error) {
		return "ok", nil
	}

	g.CheckOrExecute(context.Background(), "k1", fn)
	g.CheckOrExecute(context.Background(), "k2", fn)
	g.CheckOrExecute(context.Background(), "k3", fn) // should evict oldest

	s := g.Stats()
	if s.Evictions < 1 {
		t.Fatalf("expected at least 1 eviction, got %d", s.Evictions)
	}
}

func TestGuardConcurrentAccess(t *testing.T) {
	g := NewIdempotencyGuard(WithGuardTTL(10 * time.Second))

	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			fn := func(ctx context.Context) (interface{}, error) {
				return "ok", nil
			}
			g.CheckOrExecute(context.Background(), "concurrent-key", fn)
		}()
	}
	wg.Wait()

	s := g.Stats()
	if s.Hits+s.Misses != 100 {
		t.Fatalf("total calls=%d, want 100", s.Hits+s.Misses)
	}
}

func TestGuardErrorPropagation(t *testing.T) {
	g := NewIdempotencyGuard()

	expectedErr := errors.New("boom")
	fn := func(ctx context.Context) (interface{}, error) {
		return nil, expectedErr
	}

	_, dup, err := g.CheckOrExecute(context.Background(), "err-key", fn)
	if dup {
		t.Fatal("errors should not be cached as duplicates")
	}
	if err != expectedErr {
		t.Fatalf("expected %v, got %v", expectedErr, err)
	}
}

func TestGuardReset(t *testing.T) {
	g := NewIdempotencyGuard()

	fn := func(ctx context.Context) (interface{}, error) {
		return "ok", nil
	}

	g.CheckOrExecute(context.Background(), "k1", fn)
	g.CheckOrExecute(context.Background(), "k1", fn) // hit

	s := g.Stats()
	if s.Hits != 1 {
		t.Fatal("expected 1 hit")
	}

	g.Reset()
	s = g.Stats()
	if s.Hits != 0 || s.Misses != 0 || s.CacheSize != 0 {
		t.Fatal("reset should clear all stats")
	}

	// Key should be a miss again after reset
	_, dup, _ := g.CheckOrExecute(context.Background(), "k1", fn)
	if dup {
		t.Fatal("after reset, key should be a miss")
	}
}

func TestGuardEventCallback(t *testing.T) {
	events := make([]ArkEvent, 0)
	g := NewIdempotencyGuard(
		WithGuardEventCallback(func(e ArkEvent) {
			events = append(events, e)
		}),
	)

	fn := func(ctx context.Context) (interface{}, error) {
		return "ok", nil
	}

	g.CheckOrExecute(context.Background(), "ev-key", fn) // miss
	g.CheckOrExecute(context.Background(), "ev-key", fn) // hit

	if len(events) != 2 {
		t.Fatalf("expected 2 events, got %d", len(events))
	}
	if events[0].Type != "ark.idempotency.miss" {
		t.Errorf("expected miss event, got %s", events[0].Type)
	}
	if events[1].Type != "ark.idempotency.hit" {
		t.Errorf("expected hit event, got %s", events[1].Type)
	}
}

func TestHashKey(t *testing.T) {
	k1 := HashKey("func1", "arg1", "arg2")
	k2 := HashKey("func1", "arg1", "arg2")
	k3 := HashKey("func1", "arg1", "arg3")

	if k1 != k2 {
		t.Fatal("same args should produce same hash")
	}
	if k1 == k3 {
		t.Fatal("different args should produce different hash")
	}
	if len(k1) != 64 {
		t.Fatalf("hash should be 64 hex chars, got %d", len(k1))
	}
}
