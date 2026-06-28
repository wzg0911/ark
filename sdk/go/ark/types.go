// Package ark provides the Agent Reliability Kit (ARK) for Go.
// It mirrors the Python core module with the same API surface and behavior.
package ark

import "time"

// CircuitState represents the breaker state machine.
type CircuitState int

const (
	CircuitClosed   CircuitState = iota // normal operation
	CircuitOpen                         // failing, rejecting calls
	CircuitHalfOpen                     // testing recovery
)

func (s CircuitState) String() string {
	switch s {
	case CircuitClosed:
		return "closed"
	case CircuitOpen:
		return "open"
	case CircuitHalfOpen:
		return "half_open"
	default:
		return "unknown"
	}
}

// ArkEvent represents a reliability event emitted by ARK components.
type ArkEvent struct {
	Type      string            `json:"type"`
	Timestamp time.Time         `json:"timestamp"`
	AgentID   string            `json:"agent_id"`
	TraceID   string            `json:"trace_id"`
	SpanID    string            `json:"span_id"`
	Attrs     map[string]string `json:"attrs"`
}

// ValidationResult from OutputValidator.
type ValidationResult struct {
	Passed   bool              `json:"passed"`
	Errors   []ValidationError `json:"errors"`
	Warnings []string          `json:"warnings"`
}

// ValidationError describes a single validation failure.
type ValidationError struct {
	Field   string      `json:"field"`
	Message string      `json:"message"`
	Value   interface{} `json:"value,omitempty"`
}

// Version is the current SDK version.
const Version = "0.7.0-alpha.1"
