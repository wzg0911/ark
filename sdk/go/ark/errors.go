// Package ark — Error F9: compress errors into LLM context
//
// Gene source: 12-Factor Agents (HumanLayer) Factor 9
//
// Three core capabilities:
//  1. TruncateError() — truncate stack traces to LLM-friendly length
//  2. ErrorToLLMContext() — structure errors for LLM self-healing
//  3. ShouldRetry() — exponential backoff + retry cap + escalation path
//
// Design principles:
//   - Zero dependencies (stdlib only)
//   - Zero overhead (no allocations when unused)
//   - Serializable (error → JSON → LLM context)
//   - Thread-safe (all accumulators use sync.Mutex)

package ark

import (
	"crypto/md5"
	"errors"
	"fmt"
	"runtime/debug"
	"strings"
	"sync"
	"time"
)

// ━━━━━━━━━━ Sentinels (v0.7 core) ━━━━━━━━━━

var (
	// ErrCircuitOpen is returned when executing through an open breaker.
	ErrCircuitOpen = errors.New("ark: circuit breaker is open")

	// ErrValidationFail is a generic validation failure.
	ErrValidationFail = errors.New("ark: output validation failed")

	// ErrGuardExpired is returned when a cached guard entry has expired.
	ErrGuardExpired = errors.New("ark: idempotency guard entry expired")
)

// ValidationFailedError wraps a ValidationResult as an error.
type ValidationFailedError struct {
	Result ValidationResult
}

func (e *ValidationFailedError) Error() string {
	return fmt.Sprintf("ark: validation failed (%d errors)", len(e.Result.Errors))
}

// ━━━━━━━━━━ 1. Error Truncation (TruncateError) ━━━━━━━━━━

// TruncatedError holds a compressed error suitable for LLM context.
type TruncatedError struct {
	Type      string   `json:"type"`
	Message   string   `json:"message"`
	StackTail []string `json:"stack_tail"`
	RawHash   string   `json:"raw_hash"`
}

// TruncateError compresses an error into an LLM-friendly format.
//
// Key techniques:
//   - error message truncated to maxMsgLen (default 500)
//   - stack trace keeps only the last maxStackLines (most relevant)
//   - MD5 hash for deduplication
func TruncateError(err error, maxMsgLen int, maxStackLines int) TruncatedError {
	if maxMsgLen <= 0 {
		maxMsgLen = 500
	}
	if maxStackLines <= 0 {
		maxStackLines = 3
	}

	fullMsg := err.Error()
	truncated := fullMsg
	if len(truncated) > maxMsgLen {
		truncated = truncated[:maxMsgLen] + "..."
	}

	// Capture and trim stack trace
	stack := string(debug.Stack())
	lines := strings.Split(stack, "\n")
	var nonEmpty []string
	for _, line := range lines {
		if strings.TrimSpace(line) != "" {
			nonEmpty = append(nonEmpty, line)
		}
	}
	// Keep last N lines
	tail := nonEmpty
	if len(tail) > maxStackLines {
		tail = tail[len(tail)-maxStackLines:]
	}

	hash := fmt.Sprintf("%x", md5.Sum([]byte(fullMsg)))[:8]

	// Extract type name from error
	typeName := "error"
	if named, ok := err.(interface{ TypeName() string }); ok {
		typeName = named.TypeName()
	} else {
		// Fall back to fmt "%T" extraction
		typeStr := fmt.Sprintf("%T", err)
		if idx := strings.LastIndex(typeStr, "."); idx >= 0 {
			typeName = typeStr[idx+1:]
		} else if idx := strings.LastIndex(typeStr, "*"); idx >= 0 {
			typeName = typeStr[idx+1:]
		} else {
			typeName = typeStr
		}
		// Strip pointer prefix
		typeName = strings.TrimPrefix(typeName, "*")
	}

	return TruncatedError{
		Type:      typeName,
		Message:   truncated,
		StackTail: tail,
		RawHash:   hash,
	}
}

// ━━━━━━━━━━ 2. Feed Error to LLM Context (ErrorToLLMContext) ━━━━━━━━━━

// ErrorRecord holds a recorded failure for LLM context display.
type ErrorRecord struct {
	Type      string   `json:"type"`
	Message   string   `json:"message"`
	StackTail []string `json:"stack_tail,omitempty"`
	Attempt   int      `json:"attempt"`
	Timestamp float64  `json:"timestamp"`
	Retryable bool     `json:"retryable"`
}

// ErrorToLLMContext formats an error as a structured LLM context paragraph.
//
// Design: for LLM consumption, not human
//   - Concise (< 200 tokens)
//   - Clear: what error + which tool + attempt count
//   - Self-healing guidance: prompts LLM to try a different approach
func ErrorToLLMContext(err error, toolName string, attempt int, prevAttempts []ErrorRecord) string {
	te := TruncateError(err, 500, 3)

	var b strings.Builder
	fmt.Fprintf(&b, "[ERROR] Tool `%s` failed (attempt %d)\n", toolName, attempt)
	fmt.Fprintf(&b, "Type:    %s\n", te.Type)
	fmt.Fprintf(&b, "Message: %s\n", te.Message)

	if len(te.StackTail) > 0 {
		b.WriteString("Stack (last lines):\n")
		for _, line := range te.StackTail {
			b.WriteString(fmt.Sprintf("  %s\n", strings.TrimSpace(line)))
		}
	}

	// Self-healing guidance — hint on repeat failure
	if attempt >= 2 {
		b.WriteString("\n💡 Hint: This is a repeat failure. Consider:\n")
		b.WriteString("  - Different tool / approach\n")
		b.WriteString("  - Different input parameters\n")
		b.WriteString("  - Check input format / types\n")
		if attempt >= 3 {
			b.WriteString("  - Escalate to human if critical\n")
		}
	}

	// Previous attempts — let LLM see the pattern
	if len(prevAttempts) > 0 {
		b.WriteString(fmt.Sprintf("\nPrevious attempts (%d):\n", len(prevAttempts)))
		start := 0
		if len(prevAttempts) > 3 {
			start = len(prevAttempts) - 3
		}
		for i := start; i < len(prevAttempts); i++ {
			msg := prevAttempts[i].Message
			if len(msg) > 200 {
				msg = msg[:200]
			}
			fmt.Fprintf(&b, "  %d. [%s] %s\n", i-start+1, prevAttempts[i].Type, msg)
		}
	}

	return b.String()
}

// ━━━━━━━━━━ 3. Retry Decision (ShouldRetry) ━━━━━━━━━━

// NonRetryableTypes is the set of error type names that should never be retried.
var NonRetryableTypes = map[string]bool{
	"AuthenticationError": true,
	"PermissionError":     true,
	"ValidationError":     true,
	"NotImplementedError": true,
	"SyntaxError":         true,
	"ImportError":         true,
	"ModuleNotFoundError": true,
	"KeyboardInterrupt":   true,
	// Go-specific non-retryable types
	"*os.PathError":   true,
	"*net.ParseError": true,
}

// ShouldRetry decides whether a failed call should be retried.
//
// Rules:
//   - attempt < maxAttempts → retryable
//   - non-retryable error type → stop immediately
//   - exceeded max → escalate to human
func ShouldRetry(err error, attempt int, maxAttempts int) bool {
	if attempt >= maxAttempts {
		return false
	}

	// Check error type against non-retryable set
	typeName := fmt.Sprintf("%T", err)
	// Also try the short name
	shortName := typeName
	if idx := strings.LastIndex(shortName, "."); idx >= 0 {
		shortName = shortName[idx+1:]
	}

	if NonRetryableTypes[typeName] || NonRetryableTypes[shortName] {
		return false
	}

	return true
}

// RetryDelay computes exponential backoff delay.
//
// Formula: baseDelay * (backoffFactor ^ (attempt-1)), capped at maxDelay.
// Default: 1s, 2s, 4s, 8s, 16s, capped at 30s.
func RetryDelay(attempt int, baseDelay float64, maxDelay float64, backoffFactor float64) float64 {
	delay := baseDelay
	for i := 1; i < attempt; i++ {
		delay *= backoffFactor
	}
	if delay > maxDelay {
		return maxDelay
	}
	return delay
}

// ━━━━━━━━━━ 4. ErrorContext Accumulator (Thread-safe) ━━━━━━━━━━

// ErrorContextOption is a functional option for ErrorContext.
type ErrorContextOption func(*ErrorContext)

// WithMaxAttempts sets the maximum retry attempts for an ErrorContext.
func WithMaxAttempts(n int) ErrorContextOption {
	return func(ec *ErrorContext) { ec.MaxAttempts = n }
}

// ErrorContext accumulates failures for a tool call.
//
// Design:
//   - Each failure → one ErrorRecord
//   - Serializable to JSON for state persistence
//   - LLM can see the full failure history
//   - Thread-safe via sync.Mutex
type ErrorContext struct {
	mu          sync.Mutex
	ToolName    string        `json:"tool_name"`
	MaxAttempts int           `json:"max_attempts"`
	Records     []ErrorRecord `json:"records"`
	StartedAt   float64       `json:"started_at"`
}

// NewErrorContext creates a new error context accumulator.
func NewErrorContext(toolName string, opts ...ErrorContextOption) *ErrorContext {
	ec := &ErrorContext{
		ToolName:    toolName,
		MaxAttempts: 3,
		StartedAt:   float64(time.Now().UnixNano()) / 1e9,
	}
	for _, opt := range opts {
		opt(ec)
	}
	return ec
}

// RecordFailure logs a failure without throwing.
func (ec *ErrorContext) RecordFailure(err error, attempt int) ErrorRecord {
	te := TruncateError(err, 500, 3)
	record := ErrorRecord{
		Type:      te.Type,
		Message:   te.Message,
		StackTail: te.StackTail,
		Attempt:   attempt,
		Timestamp: float64(time.Now().UnixNano()) / 1e9,
		Retryable: ShouldRetry(err, attempt, ec.MaxAttempts),
	}

	ec.mu.Lock()
	ec.Records = append(ec.Records, record)
	ec.mu.Unlock()

	return record
}

// FailureCount returns the number of recorded failures.
func (ec *ErrorContext) FailureCount() int {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	return len(ec.Records)
}

// LastError returns the most recent error record, or nil.
func (ec *ErrorContext) LastError() *ErrorRecord {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	if len(ec.Records) == 0 {
		return nil
	}
	rec := ec.Records[len(ec.Records)-1]
	return &rec
}

// ShouldEscalate returns true when errors have exceeded the retry budget
// or encountered a non-retryable error.
func (ec *ErrorContext) ShouldEscalate() bool {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	if len(ec.Records) == 0 {
		return false
	}
	last := ec.Records[len(ec.Records)-1]
	return !last.Retryable || last.Attempt >= ec.MaxAttempts
}

// ToLLMContext renders the full error context for LLM consumption.
func (ec *ErrorContext) ToLLMContext() string {
	ec.mu.Lock()
	defer ec.mu.Unlock()

	if len(ec.Records) == 0 {
		return ""
	}

	var b strings.Builder
	fmt.Fprintf(&b, "[ERROR CONTEXT] Tool `%s` has %d failure(s)\n\n", ec.ToolName, len(ec.Records))

	for _, rec := range ec.Records {
		fmt.Fprintf(&b, "[ERROR] Tool `%s` failed (attempt %d)\n", ec.ToolName, rec.Attempt)
		fmt.Fprintf(&b, "Type:    %s\n", rec.Type)
		fmt.Fprintf(&b, "Message: %s\n", rec.Message)
		if len(rec.StackTail) > 0 {
			b.WriteString("Stack (last lines):\n")
			for _, line := range rec.StackTail {
				trimmed := strings.TrimSpace(line)
				if trimmed != "" {
					fmt.Fprintf(&b, "  %s\n", trimmed)
				}
			}
		}
		if rec.Attempt >= 2 {
			b.WriteString("\n💡 Hint: This is a repeat failure. Consider:\n")
			b.WriteString("  - Different tool / approach\n")
			b.WriteString("  - Different input parameters\n")
			b.WriteString("  - Check input format / types\n")
			if rec.Attempt >= 3 {
				b.WriteString("  - Escalate to human if critical\n")
			}
		}
		b.WriteString("\n")
	}

	if ec.shouldEscalateLocked() {
		b.WriteString("🚨 ESCALATE TO HUMAN: This tool has failed too many times.\n")
	}

	return b.String()
}

// shouldEscalateLocked is the internal, non-locking version.
func (ec *ErrorContext) shouldEscalateLocked() bool {
	if len(ec.Records) == 0 {
		return false
	}
	last := ec.Records[len(ec.Records)-1]
	return !last.Retryable || last.Attempt >= ec.MaxAttempts
}

// ToDict serializes the ErrorContext as a map.
func (ec *ErrorContext) ToDict() map[string]interface{} {
	ec.mu.Lock()
	defer ec.mu.Unlock()

	return map[string]interface{}{
		"tool_name":       ec.ToolName,
		"max_attempts":    ec.MaxAttempts,
		"records":         ec.Records,
		"started_at":      ec.StartedAt,
		"failure_count":   len(ec.Records),
		"should_escalate": ec.shouldEscalateLocked(),
	}
}

// Reset clears all recorded failures.
func (ec *ErrorContext) Reset() {
	ec.mu.Lock()
	defer ec.mu.Unlock()
	ec.Records = nil
}

// ━━━━━━━━━━ 5. WithRetry — Go-style retry wrapper ━━━━━━━━━━

// RetryConfig configures the retry behavior for WithRetry.
type RetryConfig struct {
	ToolName      string
	MaxAttempts   int
	BaseDelay     float64
	MaxDelay      float64
	BackoffFactor float64
	Fallback      func() (interface{}, error)
	OnRetry       func(attempt int, delay float64)
}

// DefaultRetryConfig returns sensible defaults.
func DefaultRetryConfig(toolName string) RetryConfig {
	return RetryConfig{
		ToolName:      toolName,
		MaxAttempts:   3,
		BaseDelay:     1.0,
		MaxDelay:      30.0,
		BackoffFactor: 2.0,
	}
}

// WithRetry wraps a function with automatic retry, error truncation, and escalation.
//
// Usage:
//
//	result, err := WithRetry(ctx, DefaultRetryConfig("send_email"), func() (interface{}, error) {
//	    return smtp.Send(to, subject)
//	})
func WithRetry(cfg RetryConfig, fn func() (interface{}, error)) (interface{}, error) {
	ec := NewErrorContext(cfg.ToolName, WithMaxAttempts(cfg.MaxAttempts))

	for attempt := 1; attempt <= cfg.MaxAttempts; attempt++ {
		result, err := fn()
		if err == nil {
			if attempt > 1 {
				// Recovery log in production would use a logger
			}
			return result, nil
		}

		ec.RecordFailure(err, attempt)

		if !ShouldRetry(err, attempt, cfg.MaxAttempts) {
			// Non-retryable or exceeded: use fallback or escalate
			if cfg.Fallback != nil {
				return cfg.Fallback()
			}
			if attempt >= cfg.MaxAttempts {
				return nil, fmt.Errorf(
					"[%s] All %d attempts failed. Last error: %s: %s",
					cfg.ToolName, cfg.MaxAttempts, typeName(err), truncateMsg(err, 200),
				)
			}
			// Non-retryable error: return as-is
			return nil, err
		}

		delay := RetryDelay(attempt, cfg.BaseDelay, cfg.MaxDelay, cfg.BackoffFactor)
		if cfg.OnRetry != nil {
			cfg.OnRetry(attempt, delay)
		}
		time.Sleep(time.Duration(delay * float64(time.Second)))
	}

	// Should be unreachable
	return nil, fmt.Errorf("[%s] Unexpected: retry loop ended without return", cfg.ToolName)
}

// ━━━━━━━━━━ Internal helpers ━━━━━━━━━━

func typeName(err error) string {
	typeStr := fmt.Sprintf("%T", err)
	// Strip package path
	if idx := strings.LastIndex(typeStr, "."); idx >= 0 {
		return typeStr[idx+1:]
	}
	return typeStr
}

func truncateMsg(err error, maxLen int) string {
	msg := err.Error()
	if len(msg) > maxLen {
		return msg[:maxLen] + "..."
	}
	return msg
}
