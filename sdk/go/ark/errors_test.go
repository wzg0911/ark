package ark

import (
	"errors"
	"fmt"
	"strings"
	"testing"
)

// ━━━━━━━━━━ 1. TruncateError ━━━━━━━━━━

func TestTruncateError_Basic(t *testing.T) {
	err := errors.New("hello world")
	result := TruncateError(err, 500, 3)

	if result.Type != "errorString" {
		t.Errorf("expected Type 'errorString', got %q", result.Type)
	}
	if result.Message != "hello world" {
		t.Errorf("expected Message 'hello world', got %q", result.Message)
	}
	if result.RawHash == "" {
		t.Error("expected non-empty RawHash")
	}
	if len(result.RawHash) != 8 {
		t.Errorf("expected RawHash length 8, got %d", len(result.RawHash))
	}
}

func TestTruncateError_LongMessage(t *testing.T) {
	longMsg := strings.Repeat("x", 1000)
	err := errors.New(longMsg)
	result := TruncateError(err, 100, 3)

	if len(result.Message) > 103 { // 100 + "..."
		t.Errorf("message too long: %d > 103", len(result.Message))
	}
	if !strings.HasSuffix(result.Message, "...") {
		t.Error("truncated message should end with '...'")
	}
}

func TestTruncateError_StackTail(t *testing.T) {
	// Call through a few frames to get a meaningful stack
	var result TruncatedError
	func() {
		func() {
			err := errors.New("nested")
			result = TruncateError(err, 500, 3)
		}()
	}()

	if result.Type != "errorString" {
		t.Errorf("expected Type 'errorString', got %q", result.Type)
	}
	// Stack tail should have some non-empty lines
	nonEmpty := 0
	for _, line := range result.StackTail {
		if strings.TrimSpace(line) != "" {
			nonEmpty++
		}
	}
	if nonEmpty < 1 {
		t.Error("expected at least 1 non-empty stack line")
	}
}

func TestTruncateError_DifferentErrorsGiveDifferentHashes(t *testing.T) {
	e1 := errors.New("error one")
	e2 := errors.New("error two")

	r1 := TruncateError(e1, 500, 3)
	r2 := TruncateError(e2, 500, 3)

	if r1.RawHash == r2.RawHash {
		t.Error("different errors should have different hashes")
	}
}

func TestTruncateError_SameErrorSameHash(t *testing.T) {
	e1 := errors.New("same message")
	e2 := errors.New("same message")

	r1 := TruncateError(e1, 500, 3)
	r2 := TruncateError(e2, 500, 3)

	if r1.RawHash != r2.RawHash {
		t.Error("same error messages should have same hash")
	}
}

// ━━━━━━━━━━ 2. ErrorToLLMContext ━━━━━━━━━━

func TestErrorToLLMContext_FirstAttempt_NoHint(t *testing.T) {
	err := errors.New("bad input")
	ctx := ErrorToLLMContext(err, "test_tool", 1, nil)

	if !strings.Contains(ctx, "[ERROR]") {
		t.Error("context should contain [ERROR]")
	}
	if !strings.Contains(ctx, "test_tool") {
		t.Error("context should contain tool name")
	}
	if !strings.Contains(ctx, "attempt 1") {
		t.Error("context should contain attempt number")
	}
	if strings.Contains(ctx, "Hint:") {
		t.Error("first attempt should not have hint")
	}
}

func TestErrorToLLMContext_RepeatAttempt_Hint(t *testing.T) {
	err := errors.New("timeout")
	ctx := ErrorToLLMContext(err, "fetch_data", 2, nil)

	if !strings.Contains(ctx, "Hint:") {
		t.Error("repeat attempt should have hint")
	}
	if !strings.Contains(ctx, "Different") {
		t.Error("hint should suggest different approach")
	}
}

func TestErrorToLLMContext_ThirdAttempt_Escalation(t *testing.T) {
	err := errors.New("boom")
	ctx := ErrorToLLMContext(err, "flaky_tool", 3, nil)

	if !strings.Contains(ctx, "Escalate") {
		t.Error("third attempt should suggest escalation")
	}
}

func TestErrorToLLMContext_PreviousAttempts_Shown(t *testing.T) {
	err := errors.New("v3")
	prev := []ErrorRecord{
		{Type: "ValueError", Message: "v1", Attempt: 1},
		{Type: "ValueError", Message: "v2", Attempt: 2},
	}
	ctx := ErrorToLLMContext(err, "tool", 3, prev)

	if !strings.Contains(ctx, "Previous attempts") {
		t.Error("context should show previous attempts")
	}
	if !strings.Contains(ctx, "v1") && !strings.Contains(ctx, "v2") {
		t.Error("context should contain previous error messages")
	}
}

func TestErrorToLLMContext_PreviousAttempts_TruncatedMessage(t *testing.T) {
	longMsg := strings.Repeat("y", 500)
	err := errors.New("v3")
	prev := []ErrorRecord{
		{Type: "ValueError", Message: longMsg, Attempt: 1},
	}
	ctx := ErrorToLLMContext(err, "tool", 3, prev)

	if !strings.Contains(ctx, "Previous attempts") {
		t.Error("context should show previous attempts even with long messages")
	}
}

// ━━━━━━━━━━ 3. ShouldRetry ━━━━━━━━━━

func TestShouldRetry_BelowLimit(t *testing.T) {
	err := errors.New("test")
	if !ShouldRetry(err, 1, 3) {
		t.Error("attempt 1 of 3 should be retryable")
	}
	if !ShouldRetry(err, 2, 3) {
		t.Error("attempt 2 of 3 should be retryable")
	}
}

func TestShouldRetry_AtLimit(t *testing.T) {
	err := errors.New("test")
	if ShouldRetry(err, 3, 3) {
		t.Error("attempt 3 of 3 should NOT be retryable")
	}
	if ShouldRetry(err, 5, 3) {
		t.Error("attempt 5 of 3 should NOT be retryable")
	}
}

// Custom error types for testing non-retryable detection.
// Note: PermissionError and NotImplementedError match entries in NonRetryableTypes.
// Validation retry-bypass uses the real ValidationError from types.go.
type PermissionError struct{ msg string }
func (e *PermissionError) Error() string { return e.msg }

type NotImplementedError struct{ msg string }
func (e *NotImplementedError) Error() string { return e.msg }

func TestShouldRetry_NonRetryableTypes(t *testing.T) {
	// These should match by type name
	tests := []struct {
		name string
		err  error
	}{
		{"PermissionError", &PermissionError{"denied"}},
		{"NotImplementedError", &NotImplementedError{"todo"}},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if ShouldRetry(tt.err, 1, 5) {
				t.Errorf("%s should not be retryable", tt.name)
			}
		})
	}
}

func TestShouldRetry_RetryableError(t *testing.T) {
	// Regular errors should be retryable
	err := errors.New("connection timeout")
	if !ShouldRetry(err, 1, 5) {
		t.Error("connection timeout should be retryable")
	}
}

// ━━━━━━━━━━ 4. RetryDelay — Exponential Backoff ━━━━━━━━━━

func TestRetryDelay_ExponentialGrowth(t *testing.T) {
	d1 := RetryDelay(1, 1.0, 30.0, 2.0)
	d2 := RetryDelay(2, 1.0, 30.0, 2.0)
	d3 := RetryDelay(3, 1.0, 30.0, 2.0)

	if d1 != 1.0 {
		t.Errorf("attempt 1 delay: expected 1.0, got %f", d1)
	}
	if d2 != 2.0 {
		t.Errorf("attempt 2 delay: expected 2.0, got %f", d2)
	}
	if d3 != 4.0 {
		t.Errorf("attempt 3 delay: expected 4.0, got %f", d3)
	}
}

func TestRetryDelay_CappedAtMax(t *testing.T) {
	d10 := RetryDelay(10, 1.0, 30.0, 2.0)
	if d10 != 30.0 {
		t.Errorf("attempt 10 delay: expected 30.0 (capped), got %f", d10)
	}
}

func TestRetryDelay_CustomBackoff(t *testing.T) {
	d1 := RetryDelay(1, 2.0, 60.0, 3.0)
	d2 := RetryDelay(2, 2.0, 60.0, 3.0)
	d3 := RetryDelay(3, 2.0, 60.0, 3.0)

	if d1 != 2.0 {
		t.Errorf("attempt 1: expected 2.0, got %f", d1)
	}
	if d2 != 6.0 {
		t.Errorf("attempt 2: expected 6.0, got %f", d2)
	}
	if d3 != 18.0 {
		t.Errorf("attempt 3: expected 18.0, got %f", d3)
	}
}

// ━━━━━━━━━━ 5. ErrorContext Accumulator ━━━━━━━━━━

func TestErrorContext_RecordAndCount(t *testing.T) {
	ec := NewErrorContext("send_email")

	err := errors.New("value error v1")
	ec.RecordFailure(err, 1)

	if ec.FailureCount() != 1 {
		t.Errorf("expected 1 failure, got %d", ec.FailureCount())
	}
	if ec.LastError() == nil {
		t.Error("expected non-nil last error")
	}
}

func TestErrorContext_EscalationAfterMax(t *testing.T) {
	ec := NewErrorContext("api_call", WithMaxAttempts(3))

	for i := 1; i <= 3; i++ {
		ec.RecordFailure(fmt.Errorf("failure %d", i), i)
	}

	if !ec.ShouldEscalate() {
		t.Error("should escalate after max attempts")
	}
}

func TestErrorContext_ImmediateEscalation_NonRetryable(t *testing.T) {
	ec := NewErrorContext("auth_call", WithMaxAttempts(3))

	err := &PermissionError{"denied"}
	ec.RecordFailure(err, 1)

	if !ec.ShouldEscalate() {
		t.Error("should escalate immediately for non-retryable error")
	}
}

func TestErrorContext_ToLLMContext_Renders(t *testing.T) {
	ec := NewErrorContext("my_tool", WithMaxAttempts(3))
	ec.RecordFailure(errors.New("test error"), 1)

	text := ec.ToLLMContext()
	if !strings.Contains(text, "my_tool") {
		t.Error("context should contain tool name")
	}
	if !strings.Contains(text, "attempt 1") {
		t.Error("context should contain attempt number")
	}
}

func TestErrorContext_ToDict_Serializable(t *testing.T) {
	ec := NewErrorContext("tool_t", WithMaxAttempts(3))
	ec.RecordFailure(errors.New("test"), 1)

	d := ec.ToDict()
	if d["tool_name"] != "tool_t" {
		t.Errorf("expected tool_name 'tool_t', got %v", d["tool_name"])
	}
	if d["failure_count"] != 1 {
		t.Errorf("expected failure_count 1, got %v", d["failure_count"])
	}
	if _, ok := d["records"].([]ErrorRecord); !ok {
		t.Error("records should be a slice of ErrorRecord")
	}
}

func TestErrorContext_EmptyContext_NoLLMOutput(t *testing.T) {
	ec := NewErrorContext("clean_tool")

	text := ec.ToLLMContext()
	if text != "" {
		t.Error("empty context should produce empty string")
	}
}

func TestErrorContext_EscalationWithEscalateText(t *testing.T) {
	ec := NewErrorContext("broken_tool", WithMaxAttempts(3))

	for i := 1; i <= 3; i++ {
		ec.RecordFailure(errors.New("fail"), i)
	}

	text := ec.ToLLMContext()
	if !strings.Contains(text, "ESCALATE") {
		t.Error("escalated context should contain ESCALATE text")
	}
}

func TestErrorContext_ShouldEscalate_Empty(t *testing.T) {
	ec := NewErrorContext("empty_tool")
	if ec.ShouldEscalate() {
		t.Error("empty context should not escalate")
	}
}

func TestErrorContext_Reset(t *testing.T) {
	ec := NewErrorContext("test")
	ec.RecordFailure(errors.New("err"), 1)
	if ec.FailureCount() != 1 {
		t.Fatal("expected 1 failure before reset")
	}

	ec.Reset()
	if ec.FailureCount() != 0 {
		t.Error("expected 0 failures after reset")
	}
}

func TestErrorContext_ConcurrentAccess(t *testing.T) {
	ec := NewErrorContext("concurrent", WithMaxAttempts(100))
	done := make(chan bool)

	for i := 0; i < 10; i++ {
		go func(id int) {
			for j := 0; j < 10; j++ {
				ec.RecordFailure(fmt.Errorf("err-%d-%d", id, j), 1)
			}
			done <- true
		}(i)
	}

	for i := 0; i < 10; i++ {
		<-done
	}

	if ec.FailureCount() != 100 {
		t.Errorf("expected 100 failures, got %d", ec.FailureCount())
	}
}

// ━━━━━━━━━━ 6. WithRetry Wrapper ━━━━━━━━━━

func TestWithRetry_Success_NoRetry(t *testing.T) {
	callCount := 0
	cfg := DefaultRetryConfig("ok")
	cfg.MaxAttempts = 3

	result, err := WithRetry(cfg, func() (interface{}, error) {
		callCount++
		return "success", nil
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "success" {
		t.Errorf("expected 'success', got %v", result)
	}
	if callCount != 1 {
		t.Errorf("expected 1 call, got %d", callCount)
	}
}

func TestWithRetry_RetryThenSucceed(t *testing.T) {
	callCount := 0
	cfg := DefaultRetryConfig("flaky")
	cfg.MaxAttempts = 3
	cfg.BaseDelay = 0.01 // fast for tests

	result, err := WithRetry(cfg, func() (interface{}, error) {
		callCount++
		if callCount < 2 {
			return nil, errors.New("transient error")
		}
		return "ok", nil
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "ok" {
		t.Errorf("expected 'ok', got %v", result)
	}
	if callCount != 2 {
		t.Errorf("expected 2 calls, got %d", callCount)
	}
}

func TestWithRetry_GiveUpAfterMax(t *testing.T) {
	cfg := DefaultRetryConfig("broken")
	cfg.MaxAttempts = 2
	cfg.BaseDelay = 0.01

	_, err := WithRetry(cfg, func() (interface{}, error) {
		return nil, errors.New("always fails")
	})

	if err == nil {
		t.Fatal("expected an error, got nil")
	}
	if !strings.Contains(err.Error(), "All 2 attempts failed") {
		t.Errorf("expected 'All 2 attempts failed' in error, got: %v", err)
	}
}

func TestWithRetry_FallbackUsed(t *testing.T) {
	cfg := DefaultRetryConfig("primary")
	cfg.MaxAttempts = 2
	cfg.BaseDelay = 0.01
	cfg.Fallback = func() (interface{}, error) {
		return "fallback_value", nil
	}

	result, err := WithRetry(cfg, func() (interface{}, error) {
		return nil, errors.New("fail")
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "fallback_value" {
		t.Errorf("expected 'fallback_value', got %v", result)
	}
}

func TestWithRetry_NonRetryableImmediateFallback(t *testing.T) {
	cfg := DefaultRetryConfig("auth")
	cfg.MaxAttempts = 5
	cfg.BaseDelay = 0.01
	cfg.Fallback = func() (interface{}, error) {
		return "unauthorized_default", nil
	}

	result, err := WithRetry(cfg, func() (interface{}, error) {
		return nil, &PermissionError{"denied"}
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "unauthorized_default" {
		t.Errorf("expected 'unauthorized_default', got %v", result)
	}
}

func TestWithRetry_NonRetryableNoFallback(t *testing.T) {
	cfg := DefaultRetryConfig("auth")
	cfg.MaxAttempts = 5
	cfg.BaseDelay = 0.01

	_, err := WithRetry(cfg, func() (interface{}, error) {
		return nil, &PermissionError{"denied"}
	})

	if err == nil {
		t.Fatal("expected an error, got nil")
	}
}

func TestWithRetry_OnRetryCallback(t *testing.T) {
	retryCalled := 0
	callCount := 0

	cfg := DefaultRetryConfig("cb_test")
	cfg.MaxAttempts = 3
	cfg.BaseDelay = 0.01
	cfg.OnRetry = func(attempt int, delay float64) {
		retryCalled++
	}

	_, _ = WithRetry(cfg, func() (interface{}, error) {
		callCount++
		return nil, errors.New("fail")
	})

	if retryCalled != 2 {
		t.Errorf("expected OnRetry called 2 times (attempts 2 and 3), got %d", retryCalled)
	}
}

// ━━━━━━━━━━ 7. Integration Tests ━━━━━━━━━━

func TestF9Integration_RetryHistoryFeedsLLMContext(t *testing.T) {
	ec := NewErrorContext("flaky_api", WithMaxAttempts(3))

	for attempt := 1; attempt <= 3; attempt++ {
		ec.RecordFailure(fmt.Errorf("timeout #%d", attempt), attempt)
	}

	state := ec.ToDict()
	if fc, ok := state["failure_count"].(int); !ok || fc != 3 {
		t.Errorf("expected failure_count 3, got %v", state["failure_count"])
	}

	if !ec.ShouldEscalate() {
		t.Error("should escalate after 3 failures")
	}

	llmText := ec.ToLLMContext()
	if !strings.Contains(llmText, "ESCALATE") {
		t.Error("LLM context should contain ESCALATE")
	}
	if !strings.Contains(llmText, "attempt 3") {
		t.Error("LLM context should mention attempt 3")
	}
}

func TestF9Integration_Full12FactorRecipe(t *testing.T) {
	// ✅ Truncation: error message won't overflow context
	longMsg := strings.Repeat("x", 10000)
	err := errors.New(longMsg)
	result := TruncateError(err, 200, 3)
	if len(result.Message) > 250 {
		t.Errorf("truncation failed: message length %d > 250", len(result.Message))
	}

	// ✅ Retry cap
	if ShouldRetry(errors.New("test"), 3, 3) {
		t.Error("should not retry at max attempts")
	}

	// ✅ Escalation path
	ec := NewErrorContext("tool_t", WithMaxAttempts(3))
	for i := 1; i <= 3; i++ {
		ec.RecordFailure(fmt.Errorf("failure %d", i), i)
	}
	if !ec.ShouldEscalate() {
		t.Error("should escalate after max attempts")
	}

	// ✅ Original error type preserved
	last := ec.LastError()
	if last == nil {
		t.Fatal("expected non-nil last error")
	}
	if last.Type == "" {
		t.Error("error type should be preserved")
	}
}

func TestF9Integration_ErrorContextWithRetry_Combined(t *testing.T) {
	// Simulate a real-world scenario: flaky API that eventually succeeds
	cfg := DefaultRetryConfig("flaky_api")
	cfg.MaxAttempts = 4
	cfg.BaseDelay = 0.01

	attempts := 0
	result, err := WithRetry(cfg, func() (interface{}, error) {
		attempts++
		if attempts <= 2 {
			return nil, fmt.Errorf("attempt %d failed", attempts)
		}
		return "recovered", nil
	})

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result != "recovered" {
		t.Errorf("expected 'recovered', got %v", result)
	}
	if attempts != 3 {
		t.Errorf("expected 3 attempts (2 fails + 1 success), got %d", attempts)
	}
}

func TestF9Integration_FallbackWithEscalation(t *testing.T) {
	cfg := DefaultRetryConfig("critical_api")
	cfg.MaxAttempts = 3
	cfg.BaseDelay = 0.01
	cfg.Fallback = func() (interface{}, error) {
		return "safe_default", nil
	}

	// All attempts fail, fallback kicks in
	result, err := WithRetry(cfg, func() (interface{}, error) {
		return nil, errors.New("critical failure")
	})

	if err != nil {
		t.Fatalf("fallback should prevent error: %v", err)
	}
	if result != "safe_default" {
		t.Errorf("expected 'safe_default', got %v", result)
	}
}
