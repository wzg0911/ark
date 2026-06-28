package ark

import (
	"testing"
)

func TestValidatorBasicPass(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{
			{Name: "name", Type: "string", Required: true},
			{Name: "age", Type: "number"},
		},
	})

	result := v.Validate("test", map[string]interface{}{
		"name": "Alice",
		"age":  30.0,
	})

	if !result.Passed {
		t.Fatalf("expected pass, got errors: %v", result.Errors)
	}
}

func TestValidatorRequiredMissing(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{
			{Name: "name", Type: "string", Required: true},
		},
	})

	result := v.Validate("test", map[string]interface{}{})
	if result.Passed {
		t.Fatal("expected fail for missing required field")
	}
	if len(result.Errors) != 1 {
		t.Fatalf("expected 1 error, got %d", len(result.Errors))
	}
}

func TestValidatorTypeMismatch(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{
			{Name: "count", Type: "number", Required: true},
		},
	})

	result := v.Validate("test", map[string]interface{}{
		"count": "not-a-number",
	})
	if result.Passed {
		t.Fatal("expected fail for type mismatch")
	}
}

func TestValidatorStringConstraints(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{
			{Name: "code", Type: "string", MinLen: intPtr(3), MaxLen: intPtr(10), Pattern: "^[A-Z]{3,10}$"},
		},
	})

	// Valid
	r := v.Validate("test", map[string]interface{}{"code": "ABC"})
	if !r.Passed {
		t.Fatalf("ABC should pass: %v", r.Errors)
	}

	// Too short
	r = v.Validate("test", map[string]interface{}{"code": "AB"})
	if r.Passed {
		t.Fatal("AB should fail (too short)")
	}

	// Pattern mismatch
	r = v.Validate("test", map[string]interface{}{"code": "abc"})
	if r.Passed {
		t.Fatal("abc should fail (lowercase)")
	}
}

func TestValidatorNumberBounds(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{
			{Name: "score", Type: "number", Min: float64Ptr(0), Max: float64Ptr(100)},
		},
	})

	r := v.Validate("test", map[string]interface{}{"score": 50.0})
	if !r.Passed {
		t.Fatal("50 should pass")
	}

	r = v.Validate("test", map[string]interface{}{"score": -1.0})
	if r.Passed {
		t.Fatal("-1 should fail (below min)")
	}

	r = v.Validate("test", map[string]interface{}{"score": 101.0})
	if r.Passed {
		t.Fatal("101 should fail (above max)")
	}
}

func TestValidatorEnum(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{
			{Name: "status", Type: "string", Enum: []interface{}{"active", "inactive", "pending"}},
		},
	})

	r := v.Validate("test", map[string]interface{}{"status": "active"})
	if !r.Passed {
		t.Fatal("active should pass enum")
	}

	r = v.Validate("test", map[string]interface{}{"status": "deleted"})
	if r.Passed {
		t.Fatal("deleted should fail enum")
	}
}

func TestValidatorNestedObject(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("user", ValidationSchema{
		Fields: []FieldRule{
			{Name: "name", Type: "string", Required: true},
			{Name: "address", Type: "object", Children: []FieldRule{
				{Name: "city", Type: "string", Required: true},
				{Name: "zip", Type: "string"},
			}},
		},
	})

	// Valid
	r := v.Validate("user", map[string]interface{}{
		"name": "Bob",
		"address": map[string]interface{}{
			"city": "NYC",
		},
	})
	if !r.Passed {
		t.Fatalf("expected pass: %v", r.Errors)
	}

	// Missing nested required
	r = v.Validate("user", map[string]interface{}{
		"name":    "Bob",
		"address": map[string]interface{}{},
	})
	if r.Passed {
		t.Fatal("expected fail: missing address.city")
	}
}

func TestValidatorUnknownSchema(t *testing.T) {
	v := NewOutputValidator()
	r := v.Validate("nonexistent", map[string]interface{}{})
	if r.Passed {
		t.Fatal("unknown schema should fail")
	}
}

func TestValidatorStats(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{
			{Name: "x", Type: "number", Required: true},
		},
	})

	v.Validate("test", map[string]interface{}{"x": 1.0})  // pass
	v.Validate("test", map[string]interface{}{"x": "bad"}) // fail

	s := v.Stats()
	if s.Passed != 1 || s.Failed != 1 || s.Total != 2 {
		t.Fatalf("stats: passed=%d failed=%d total=%d", s.Passed, s.Failed, s.Total)
	}
}

func TestValidatorReset(t *testing.T) {
	v := NewOutputValidator()
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{{Name: "x", Type: "number", Required: true}},
	})

	v.Validate("test", map[string]interface{}{"x": 1.0})
	v.Reset()

	s := v.Stats()
	if s.Total != 0 {
		t.Fatal("reset should zero stats")
	}
}

func TestValidatorEventCallback(t *testing.T) {
	events := make([]ArkEvent, 0)
	v := NewOutputValidator(WithValidatorEventCallback(func(e ArkEvent) {
		events = append(events, e)
	}))
	v.RegisterSchema("test", ValidationSchema{
		Fields: []FieldRule{{Name: "x", Type: "number", Required: true}},
	})

	v.Validate("test", map[string]interface{}{"x": 1.0})   // pass
	v.Validate("test", map[string]interface{}{"x": "bad"}) // fail

	if len(events) != 2 {
		t.Fatalf("expected 2 events, got %d", len(events))
	}
	if events[0].Type != "ark.validation.pass" {
		t.Errorf("expected pass, got %s", events[0].Type)
	}
	if events[1].Type != "ark.validation.fail" {
		t.Errorf("expected fail, got %s", events[1].Type)
	}
}

func TestValidationFailedError(t *testing.T) {
	e := &ValidationFailedError{
		Result: ValidationResult{
			Passed: false,
			Errors: []ValidationError{
				{Field: "x", Message: "bad"},
				{Field: "y", Message: "also bad"},
			},
		},
	}
	if e.Error() != "ark: validation failed (2 errors)" {
		t.Errorf("unexpected error message: %s", e.Error())
	}
}

// Helpers
func intPtr(i int) *int       { return &i }
func float64Ptr(f float64) *float64 { return &f }
