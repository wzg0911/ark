package ark

import (
	"regexp"
	"sync"

	"github.com/wzg0911/ark-go/internal/clock"
)

// ValidatorOption is a functional option for OutputValidator.
type ValidatorOption func(*OutputValidator)

// WithValidatorEventCallback sets a callback for validation events.
func WithValidatorEventCallback(fn func(ArkEvent)) ValidatorOption {
	return func(v *OutputValidator) { v.onEvent = fn }
}

// ValidatorStats tracks OutputValidator metrics.
type ValidatorStats struct {
	Passed int64 `json:"passed"`
	Failed int64 `json:"failed"`
	Total  int64 `json:"total"`
}

// FieldRule defines a validation rule for a single field.
type FieldRule struct {
	Name     string        `json:"name"`
	Type     string        `json:"type"` // "string", "number", "bool", "array", "object"
	Required bool          `json:"required"`
	Min      *float64      `json:"min,omitempty"`
	Max      *float64      `json:"max,omitempty"`
	Pattern  string        `json:"pattern,omitempty"`
	MinLen   *int          `json:"min_len,omitempty"`
	MaxLen   *int          `json:"max_len,omitempty"`
	Enum     []interface{} `json:"enum,omitempty"`
	Children []FieldRule   `json:"children,omitempty"` // for nested objects

	compiledPattern *regexp.Regexp
}

// ValidationSchema groups field rules under a name.
type ValidationSchema struct {
	Fields []FieldRule `json:"fields"`
}

// OutputValidator validates structured output against registered schemas.
type OutputValidator struct {
	schemas map[string]ValidationSchema
	mu      sync.RWMutex
	stats   ValidatorStats
	onEvent func(ArkEvent)
}

// NewOutputValidator creates a new validator.
func NewOutputValidator(opts ...ValidatorOption) *OutputValidator {
	v := &OutputValidator{
		schemas: make(map[string]ValidationSchema),
	}
	for _, opt := range opts {
		opt(v)
	}
	return v
}

// RegisterSchema adds a validation schema.
func (v *OutputValidator) RegisterSchema(name string, schema ValidationSchema) {
	// Pre-compile regex patterns
	for i, f := range schema.Fields {
		if f.Pattern != "" {
			compiled, err := regexp.Compile(f.Pattern)
			if err == nil {
				schema.Fields[i].compiledPattern = compiled
			}
		}
		for j, child := range f.Children {
			if child.Pattern != "" {
				compiled, err := regexp.Compile(child.Pattern)
				if err == nil {
					schema.Fields[i].Children[j].compiledPattern = compiled
				}
			}
		}
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	v.schemas[name] = schema
}

// Validate checks data against the named schema.
func (v *OutputValidator) Validate(schemaName string, data map[string]interface{}) ValidationResult {
	v.mu.RLock()
	schema, ok := v.schemas[schemaName]
	v.mu.RUnlock()

	v.mu.Lock()
	v.stats.Total++
	v.mu.Unlock()

	if !ok {
		v.mu.Lock()
		v.stats.Failed++
		v.mu.Unlock()
		return ValidationResult{
			Passed: false,
			Errors: []ValidationError{{
				Field:   "(schema)",
				Message: "unknown schema: " + schemaName,
			}},
		}
	}

	result := v.validateFields(schema.Fields, data, "")

	v.mu.Lock()
	if result.Passed {
		v.stats.Passed++
	} else {
		v.stats.Failed++
	}
	v.mu.Unlock()

	v.emit(result)
	return result
}

func (v *OutputValidator) validateFields(fields []FieldRule, data map[string]interface{}, prefix string) ValidationResult {
	var result ValidationResult
	result.Passed = true

	for _, field := range fields {
		fullName := field.Name
		if prefix != "" {
			fullName = prefix + "." + field.Name
		}

		val, exists := data[field.Name]

		// Check required
		if field.Required && (!exists || val == nil) {
			result.Passed = false
			result.Errors = append(result.Errors, ValidationError{
				Field:   fullName,
				Message: "required field missing",
			})
			continue
		}

		if !exists || val == nil {
			continue // optional and missing → skip
		}

		// Type check
		if !v.checkType(field.Type, val) {
			result.Passed = false
			result.Errors = append(result.Errors, ValidationError{
				Field:   fullName,
				Message: "expected type " + field.Type,
				Value:   val,
			})
			continue
		}

		// String-specific checks
		if field.Type == "string" {
			s, _ := val.(string)
			if field.MinLen != nil && len(s) < *field.MinLen {
				result.Passed = false
				result.Errors = append(result.Errors, ValidationError{
					Field:   fullName,
					Message: "string too short",
					Value:   val,
				})
			}
			if field.MaxLen != nil && len(s) > *field.MaxLen {
				result.Passed = false
				result.Errors = append(result.Errors, ValidationError{
					Field:   fullName,
					Message: "string too long",
					Value:   val,
				})
			}
			if field.compiledPattern != nil && !field.compiledPattern.MatchString(s) {
				result.Passed = false
				result.Errors = append(result.Errors, ValidationError{
					Field:   fullName,
					Message: "pattern mismatch: " + field.Pattern,
					Value:   val,
				})
			}
		}

		// Number-specific checks
		if field.Type == "number" {
			var n float64
			switch v := val.(type) {
			case float64:
				n = v
			case int:
				n = float64(v)
			case int64:
				n = float64(v)
			default:
				continue // type already checked
			}
			if field.Min != nil && n < *field.Min {
				result.Passed = false
				result.Errors = append(result.Errors, ValidationError{
					Field:   fullName,
					Message: "value below minimum",
					Value:   val,
				})
			}
			if field.Max != nil && n > *field.Max {
				result.Passed = false
				result.Errors = append(result.Errors, ValidationError{
					Field:   fullName,
					Message: "value above maximum",
					Value:   val,
				})
			}
		}

		// Enum check
		if len(field.Enum) > 0 {
			if !v.inEnum(field.Enum, val) {
				result.Passed = false
				result.Errors = append(result.Errors, ValidationError{
					Field:   fullName,
					Message: "value not in enum",
					Value:   val,
				})
			}
		}

		// Nested object
		if field.Type == "object" && len(field.Children) > 0 {
			nested, ok := val.(map[string]interface{})
			if ok {
				nestedResult := v.validateFields(field.Children, nested, fullName)
				if !nestedResult.Passed {
					result.Passed = false
					result.Errors = append(result.Errors, nestedResult.Errors...)
				}
			}
		}
	}

	return result
}

func (v *OutputValidator) checkType(typ string, val interface{}) bool {
	switch typ {
	case "string":
		_, ok := val.(string)
		return ok
	case "number":
		switch val.(type) {
		case float64, int, int64, float32:
			return true
		default:
			return false
		}
	case "bool":
		_, ok := val.(bool)
		return ok
	case "array":
		_, ok := val.([]interface{})
		return ok
	case "object":
		_, ok := val.(map[string]interface{})
		return ok
	default:
		return true // unknown type = accept
	}
}

func (v *OutputValidator) inEnum(enum []interface{}, val interface{}) bool {
	for _, e := range enum {
		if e == val {
			return true
		}
	}
	return false
}

// Stats returns validator statistics.
func (v *OutputValidator) Stats() ValidatorStats {
	v.mu.RLock()
	defer v.mu.RUnlock()
	return v.stats
}

// Reset clears statistics.
func (v *OutputValidator) Reset() {
	v.mu.Lock()
	defer v.mu.Unlock()
	v.stats = ValidatorStats{}
}

func (v *OutputValidator) emit(result ValidationResult) {
	if v.onEvent == nil {
		return
	}
	eventType := "ark.validation.pass"
	if !result.Passed {
		eventType = "ark.validation.fail"
	}
	v.onEvent(ArkEvent{
		Type:      eventType,
		Timestamp: clock.RealClock{}.Now(),
		Attrs: map[string]string{
			"passed": boolToStr(result.Passed),
		},
	})
}

func boolToStr(b bool) string {
	if b {
		return "true"
	}
	return "false"
}
