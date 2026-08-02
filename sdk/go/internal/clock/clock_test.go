package clock

import (
	"testing"
	"time"
)

func TestRealClock(t *testing.T) {
	c := RealClock{}
	now := c.Now()
	if now.IsZero() {
		t.Fatal("RealClock.Now() should return non-zero time")
	}
}

func TestFixedClock(t *testing.T) {
	fixed := time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)
	c := &FixedClock{T: fixed}

	if !c.Now().Equal(fixed) {
		t.Fatal("FixedClock.Now() should return fixed time")
	}

	since := c.Since(fixed.Add(-1 * time.Hour))
	if since != time.Hour {
		t.Fatalf("FixedClock.Since() = %v, want %v", since, time.Hour)
	}
}
