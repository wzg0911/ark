package ark

import (
	"errors"
	"fmt"
)

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
