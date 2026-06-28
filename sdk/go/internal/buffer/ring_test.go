package buffer

import (
	"testing"
)

func TestRingBufferPush(t *testing.T) {
	rb := New[int](3)

	if rb.Len() != 0 {
		t.Fatal("new buffer should be empty")
	}

	rb.Push(1)
	rb.Push(2)
	if rb.Len() != 2 {
		t.Fatalf("len=%d, want 2", rb.Len())
	}
	if rb.Full() {
		t.Fatal("should not be full at 2/3")
	}

	rb.Push(3)
	if rb.Len() != 3 {
		t.Fatalf("len=%d, want 3", rb.Len())
	}
	if !rb.Full() {
		t.Fatal("should be full at 3/3")
	}
}

func TestRingBufferOverflow(t *testing.T) {
	rb := New[int](3)
	rb.Push(1)
	rb.Push(2)
	rb.Push(3)
	rb.Push(4) // overwrites 1
	rb.Push(5) // overwrites 2

	items := rb.Drain()
	if len(items) != 3 {
		t.Fatalf("drain len=%d, want 3", len(items))
	}
	// Should contain 3, 4, 5
	expected := []int{3, 4, 5}
	for i, v := range items {
		if v != expected[i] {
			t.Errorf("items[%d]=%d, want %d", i, v, expected[i])
		}
	}
}

func TestRingBufferDrainEmpties(t *testing.T) {
	rb := New[int](5)
	rb.Push(1)
	rb.Push(2)
	rb.Drain()

	if rb.Len() != 0 {
		t.Fatal("buffer should be empty after drain")
	}
	if rb.Full() {
		t.Fatal("buffer should not be full after drain")
	}
}

func TestRingBufferString(t *testing.T) {
	rb := New[string](2)
	rb.Push("hello")
	rb.Push("world")

	if !rb.Full() {
		t.Fatal("should be full")
	}

	items := rb.Drain()
	if len(items) != 2 {
		t.Fatalf("len=%d, want 2", len(items))
	}
	if items[0] != "hello" || items[1] != "world" {
		t.Errorf("unexpected items: %v", items)
	}
}
