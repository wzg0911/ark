// Package clock provides a time abstraction for testable code.
package clock

import "time"

// Clock abstracts time operations to enable deterministic testing.
type Clock interface {
	Now() time.Time
	Since(t time.Time) time.Duration
}

// RealClock uses the system clock.
type RealClock struct{}

func (RealClock) Now() time.Time                  { return time.Now() }
func (RealClock) Since(t time.Time) time.Duration { return time.Since(t) }

// FixedClock returns a fixed time — useful for testing.
// Use as pointer (&FixedClock{}) so mutations are visible through the Clock interface.
type FixedClock struct {
	T time.Time
}

func (c *FixedClock) Now() time.Time                  { return c.T }
func (c *FixedClock) Since(t time.Time) time.Duration { return c.T.Sub(t) }
