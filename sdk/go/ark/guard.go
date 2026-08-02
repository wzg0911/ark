package ark

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"sync"
	"time"

	"github.com/wzg0911/ark-go/internal/clock"
)

// GuardOption is a functional option for IdempotencyGuard.
type GuardOption func(*IdempotencyGuard)

// WithGuardTTL sets the cache TTL for duplicate detection.
func WithGuardTTL(d time.Duration) GuardOption {
	return func(g *IdempotencyGuard) { g.ttl = d }
}

// WithGuardMaxSize sets the max cache entries before LRU eviction.
func WithGuardMaxSize(n int) GuardOption {
	return func(g *IdempotencyGuard) { g.maxSize = n }
}

// WithGuardClock injects a clock for testing.
func WithGuardClock(c clock.Clock) GuardOption {
	return func(g *IdempotencyGuard) { g.clock = c }
}

// WithGuardEventCallback sets a callback for each ArkEvent emitted.
func WithGuardEventCallback(fn func(ArkEvent)) GuardOption {
	return func(g *IdempotencyGuard) { g.onEvent = fn }
}

// GuardStats tracks IdempotencyGuard metrics.
type GuardStats struct {
	Hits      int64 `json:"hits"`
	Misses    int64 `json:"misses"`
	Evictions int64 `json:"evictions"`
	CacheSize int   `json:"cache_size"`
}

type idempotencyEntry struct {
	result    interface{}
	timestamp time.Time
}

// IdempotencyGuard prevents duplicate executions within a TTL window.
type IdempotencyGuard struct {
	mu      sync.RWMutex
	cache   map[string]idempotencyEntry
	ttl     time.Duration
	maxSize int
	clock   clock.Clock
	stats   GuardStats
	onEvent func(ArkEvent)
}

// NewIdempotencyGuard creates a new guard with sensible defaults.
func NewIdempotencyGuard(opts ...GuardOption) *IdempotencyGuard {
	g := &IdempotencyGuard{
		cache:   make(map[string]idempotencyEntry),
		ttl:     5 * time.Minute,
		maxSize: 10000,
		clock:   clock.RealClock{},
	}
	for _, opt := range opts {
		opt(g)
	}
	return g
}

// CheckOrExecute checks if key was seen within TTL. If so, returns cached result.
// Otherwise executes fn, caches the result, and returns it.
// Returns (result, wasDuplicate, error).
func (g *IdempotencyGuard) CheckOrExecute(
	ctx context.Context,
	key string,
	fn func(context.Context) (interface{}, error),
) (interface{}, bool, error) {
	// Fast path: check cache
	g.mu.RLock()
	entry, ok := g.cache[key]
	g.mu.RUnlock()

	if ok && g.clock.Since(entry.timestamp) < g.ttl {
		g.mu.Lock()
		g.stats.Hits++
		g.mu.Unlock()
		g.emit("ark.idempotency.hit", key)
		return entry.result, true, nil
	}

	// Execute function
	result, err := fn(ctx)
	if err != nil {
		return nil, false, err
	}

	// Cache result
	g.mu.Lock()
	g.cache[key] = idempotencyEntry{
		result:    result,
		timestamp: g.clock.Now(),
	}
	g.stats.Misses++

	// LRU eviction if over maxSize
	if g.maxSize > 0 && len(g.cache) > g.maxSize {
		g.evictOldestLocked()
	}
	g.mu.Unlock()

	g.emit("ark.idempotency.miss", key)
	return result, false, nil
}

// evictOldestLocked evicts the oldest entry. Must hold write lock.
func (g *IdempotencyGuard) evictOldestLocked() {
	var oldestKey string
	var oldestTime time.Time
	first := true
	for k, e := range g.cache {
		if first || e.timestamp.Before(oldestTime) {
			oldestKey = k
			oldestTime = e.timestamp
			first = false
		}
	}
	if oldestKey != "" {
		delete(g.cache, oldestKey)
		g.stats.Evictions++
	}
}

// Stats returns a snapshot of guard statistics.
func (g *IdempotencyGuard) Stats() GuardStats {
	g.mu.RLock()
	defer g.mu.RUnlock()
	s := g.stats
	s.CacheSize = len(g.cache)
	return s
}

// Reset clears all cached entries and resets stats.
func (g *IdempotencyGuard) Reset() {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.cache = make(map[string]idempotencyEntry)
	g.stats = GuardStats{}
}

// HashKey returns a SHA-256 hash of the input suitable as a guard key.
func HashKey(args ...string) string {
	h := sha256.New()
	for _, a := range args {
		h.Write([]byte(a))
	}
	return hex.EncodeToString(h.Sum(nil))
}

func (g *IdempotencyGuard) emit(eventType, key string) {
	if g.onEvent == nil {
		return
	}
	g.onEvent(ArkEvent{
		Type:      eventType,
		Timestamp: g.clock.Now(),
		Attrs: map[string]string{
			"key": key,
		},
	})
}
