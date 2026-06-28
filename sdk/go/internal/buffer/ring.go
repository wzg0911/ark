// Package buffer provides a generic ring buffer for OTel event batching.
package buffer

import "sync"

// RingBuffer is a thread-safe fixed-size ring buffer.
type RingBuffer[T any] struct {
	mu    sync.Mutex
	items []T
	head  int
	size  int
	cap   int
}

// New creates a new ring buffer with the given capacity.
func New[T any](capacity int) *RingBuffer[T] {
	return &RingBuffer[T]{
		items: make([]T, capacity),
		cap:   capacity,
	}
}

// Push adds an item. Returns true if the buffer is now full.
func (r *RingBuffer[T]) Push(item T) bool {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.items[(r.head+r.size)%r.cap] = item
	if r.size < r.cap {
		r.size++
	} else {
		r.head = (r.head + 1) % r.cap
	}
	return r.size >= r.cap
}

// Drain returns all items and empties the buffer.
func (r *RingBuffer[T]) Drain() []T {
	r.mu.Lock()
	defer r.mu.Unlock()

	out := make([]T, r.size)
	for i := 0; i < r.size; i++ {
		out[i] = r.items[(r.head+i)%r.cap]
	}
	r.head = 0
	r.size = 0
	return out
}

// Len returns the current number of items.
func (r *RingBuffer[T]) Len() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.size
}

// Full returns true if the buffer is at capacity.
func (r *RingBuffer[T]) Full() bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.size >= r.cap
}
