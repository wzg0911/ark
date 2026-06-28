// Package ark — Agent Reliability Kit for Go.
//
// ARK provides trust infrastructure for AI agents:
//   - IdempotencyGuard: prevent duplicate agent calls
//   - CircuitBreaker: fail fast when downstream is unhealthy
//   - OutputValidator: schema-based output validation
//   - OTelExporter: emit reliability events to OpenTelemetry
//
// Usage:
//
//	guard := ark.NewIdempotencyGuard(ark.WithGuardTTL(5 * time.Minute))
//	result, dup, err := guard.CheckOrExecute(ctx, "key-123", myFunc)
//
// For full examples, see examples/basic/main.go.
package ark
