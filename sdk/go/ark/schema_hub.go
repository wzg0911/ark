package ark

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
)

// SchemaMeta holds metadata for a registered schema.
type SchemaMeta struct {
	Name        string   `json:"name"`
	Version     string   `json:"version"`
	Author      string   `json:"author"`
	Category    string   `json:"category"`
	Tags        []string `json:"tags"`
	Description string   `json:"description"`
	Source      string   `json:"source"` // "local" | "remote"
	Downloads   int      `json:"downloads"`
	Rating      float64  `json:"rating"`
}

// SchemaHub is a community-driven schema registry and discovery center.
// It mirrors the Python SchemaHub with 13 built-in business schemas.
type SchemaHub struct {
	schemas map[string]ValidationSchema
	meta    map[string]SchemaMeta
	mu      sync.RWMutex
}

// Predefined categories matching the Python SDK.
var Categories = []string{
	"payment",
	"email",
	"github",
	"database",
	"http",
	"file",
	"messaging",
	"project",
	"ai",
	"security",
	"general",
}

// NewSchemaHub creates a SchemaHub with 13 built-in schemas.
func NewSchemaHub() *SchemaHub {
	h := &SchemaHub{
		schemas: make(map[string]ValidationSchema),
		meta:    make(map[string]SchemaMeta),
	}
	h.registerBuiltins()
	return h
}

// Register adds a schema with metadata to the hub.
func (h *SchemaHub) Register(name string, schema ValidationSchema, meta SchemaMeta) {
	meta.Name = name
	if meta.Source == "" {
		meta.Source = "local"
	}
	if meta.Version == "" {
		meta.Version = "1.0.0"
	}
	if meta.Category == "" {
		meta.Category = "general"
	}
	if meta.Author == "" {
		meta.Author = "community"
	}

	h.mu.Lock()
	defer h.mu.Unlock()
	h.schemas[name] = schema
	h.meta[name] = meta
}

// Get returns a registered schema by name.
func (h *SchemaHub) Get(name string) (ValidationSchema, bool) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	s, ok := h.schemas[name]
	return s, ok
}

// GetMeta returns metadata for a registered schema.
func (h *SchemaHub) GetMeta(name string) (SchemaMeta, bool) {
	h.mu.RLock()
	defer h.mu.RUnlock()
	m, ok := h.meta[name]
	return m, ok
}

// Available returns all registered schema names sorted.
func (h *SchemaHub) Available() []string {
	h.mu.RLock()
	defer h.mu.RUnlock()
	names := make([]string, 0, len(h.schemas))
	for n := range h.schemas {
		names = append(names, n)
	}
	sort.Strings(names)
	return names
}

// Categories returns all unique categories across registered schemas.
func (h *SchemaHub) Categories() []string {
	h.mu.RLock()
	defer h.mu.RUnlock()
	seen := make(map[string]bool)
	for _, m := range h.meta {
		seen[m.Category] = true
	}
	cats := make([]string, 0, len(seen))
	for c := range seen {
		cats = append(cats, c)
	}
	sort.Strings(cats)
	return cats
}

// Search finds schemas by query, category, tags, or author.
// All filters are AND logic.
func (h *SchemaHub) Search(query, category string, tags []string, author string) []SchemaMeta {
	h.mu.RLock()
	defer h.mu.RUnlock()

	var results []SchemaMeta
	for name, m := range h.meta {
		// Query filter: match against name or description
		if query != "" {
			q := strings.ToLower(query)
			if !strings.Contains(strings.ToLower(name), q) &&
				!strings.Contains(strings.ToLower(m.Description), q) {
				continue
			}
		}
		// Category filter
		if category != "" && m.Category != category {
			continue
		}
		// Tags filter (AND)
		if len(tags) > 0 {
			hasAll := true
			for _, t := range tags {
				found := false
				for _, mt := range m.Tags {
					if mt == t {
						found = true
						break
					}
				}
				if !found {
					hasAll = false
					break
				}
			}
			if !hasAll {
				continue
			}
		}
		// Author filter
		if author != "" && m.Author != author {
			continue
		}
		results = append(results, m)
	}
	return results
}

// ListByCategory groups schemas by category.
func (h *SchemaHub) ListByCategory() map[string][]SchemaMeta {
	h.mu.RLock()
	defer h.mu.RUnlock()

	result := make(map[string][]SchemaMeta)
	for _, m := range h.meta {
		result[m.Category] = append(result[m.Category], m)
	}
	return result
}

// Validate checks data against a registered schema.
func (h *SchemaHub) Validate(name string, data map[string]interface{}) (ValidationResult, error) {
	schema, ok := h.Get(name)
	if !ok {
		return ValidationResult{Passed: false}, fmt.Errorf("schema not found: %s", name)
	}
	v := NewOutputValidator()
	v.RegisterSchema(name, schema)
	return v.Validate(name, data), nil
}

// Stats returns hub-wide statistics.
func (h *SchemaHub) Stats() map[string]interface{} {
	h.mu.RLock()
	defer h.mu.RUnlock()

	cats := h.ListByCategory()
	byCategory := make(map[string]int)
	for k, v := range cats {
		byCategory[k] = len(v)
	}

	allTags := make(map[string]bool)
	authors := make(map[string]bool)
	for _, m := range h.meta {
		for _, t := range m.Tags {
			allTags[t] = true
		}
		authors[m.Author] = true
	}

	return map[string]interface{}{
		"total_schemas": len(h.schemas),
		"categories":    len(cats),
		"by_category":   byCategory,
		"total_tags":    len(allTags),
		"authors":       len(authors),
	}
}

// ─── Import / Export ───

// schemaFile represents a JSON schema definition file.
type schemaFile struct {
	Name        string               `json:"name"`
	Version     string               `json:"version"`
	Author      string               `json:"author"`
	Category    string               `json:"category"`
	Tags        []string             `json:"tags"`
	Description string               `json:"description"`
	Fields      []schemaFileField    `json:"fields"`
}

type schemaFileField struct {
	Name        string `json:"name"`
	Type        string `json:"type"`
	Required    bool   `json:"required"`
	Min         *float64 `json:"min,omitempty"`
	Max         *float64 `json:"max,omitempty"`
	Pattern     string `json:"pattern,omitempty"`
	MinLen      *int    `json:"min_len,omitempty"`
	MaxLen      *int    `json:"max_len,omitempty"`
	Description string `json:"description"`
}

// ImportDir loads all .json schema files from a directory into the hub.
// Returns the count of successfully loaded schemas.
func (h *SchemaHub) ImportDir(dir string) int {
	entries, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return 0
	}

	count := 0
	for _, entry := range entries {
		data, err := os.ReadFile(entry)
		if err != nil {
			continue
		}
		var sf schemaFile
		if err := json.Unmarshal(data, &sf); err != nil {
			continue
		}
		if sf.Name == "" || len(sf.Fields) == 0 {
			continue
		}

		// Build FieldRules from file fields
		fields := make([]FieldRule, len(sf.Fields))
		for i, f := range sf.Fields {
			fields[i] = FieldRule{
				Name:     f.Name,
				Type:     f.Type,
				Required: f.Required,
				Min:      f.Min,
				Max:      f.Max,
				Pattern:  f.Pattern,
				MinLen:   f.MinLen,
				MaxLen:   f.MaxLen,
			}
		}

		meta := SchemaMeta{
			Name:        sf.Name,
			Version:     orDefault(sf.Version, "1.0.0"),
			Author:      orDefault(sf.Author, "community"),
			Category:    orDefault(sf.Category, "general"),
			Tags:        sf.Tags,
			Description: sf.Description,
			Source:      "local",
		}

		h.Register(sf.Name, ValidationSchema{Fields: fields}, meta)
		count++
	}
	return count
}

// exportEntry represents a schema for JSON export.
type exportEntry struct {
	Name        string   `json:"name"`
	Version     string   `json:"version"`
	Author      string   `json:"author"`
	Category    string   `json:"category"`
	Tags        []string `json:"tags"`
	Description string   `json:"description"`
	Fields      []exportField `json:"fields"`
}

type exportField struct {
	Name        string  `json:"name"`
	Type        string  `json:"type"`
	Required    bool    `json:"required"`
	Min         *float64 `json:"min,omitempty"`
	Max         *float64 `json:"max,omitempty"`
	Pattern     string  `json:"pattern,omitempty"`
	MinLen      *int     `json:"min_len,omitempty"`
	MaxLen      *int     `json:"max_len,omitempty"`
}

// ExportJSON writes all schemas to a JSON file (for community import).
func (h *SchemaHub) ExportJSON(path string) error {
	h.mu.RLock()
	defer h.mu.RUnlock()

	var entries []exportEntry
	for name, schema := range h.schemas {
		m := h.meta[name]
		fields := make([]exportField, len(schema.Fields))
		for i, f := range schema.Fields {
			fields[i] = exportField{
				Name:     f.Name,
				Type:     f.Type,
				Required: f.Required,
				Min:      f.Min,
				Max:      f.Max,
				Pattern:  f.Pattern,
				MinLen:   f.MinLen,
				MaxLen:   f.MaxLen,
			}
		}
		entries = append(entries, exportEntry{
			Name:        name,
			Version:     m.Version,
			Author:      m.Author,
			Category:    m.Category,
			Tags:        m.Tags,
			Description: m.Description,
			Fields:      fields,
		})
	}

	data, err := json.MarshalIndent(entries, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0644)
}

// ExportMetaJSON writes schema metadata as JSON (lightweight search index).
func (h *SchemaHub) ExportMetaJSON(path string) error {
	h.mu.RLock()
	defer h.mu.RUnlock()

	var metas []SchemaMeta
	for _, m := range h.meta {
		metas = append(metas, m)
	}
	sort.Slice(metas, func(i, j int) bool { return metas[i].Name < metas[j].Name })

	data, err := json.MarshalIndent(metas, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0644)
}

// ─── 13 Built-in Schemas ───

func (h *SchemaHub) registerBuiltins() {
	min1 := 1
	min5 := 5
	max256 := 256
	max998 := 998
	usdMin := 0.01

	builtins := []struct {
		name   string
		fields []FieldRule
		meta   SchemaMeta
	}{
		// ── Payment ──
		{
			name: "stripe.charge",
			fields: []FieldRule{
				{Name: "amount", Type: "number", Required: true, Min: &usdMin},
				{Name: "currency", Type: "string", Required: true, Pattern: `^[a-z]{3}$`},
				{Name: "description", Type: "string"},
				{Name: "customer", Type: "string"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "payment",
				Tags: []string{"stripe", "charge", "payment"}, Description: "Stripe charge request schema"},
		},
		{
			name: "stripe.refund",
			fields: []FieldRule{
				{Name: "charge_id", Type: "string", Required: true, MinLen: &min5},
				{Name: "amount", Type: "number", Min: &usdMin},
				{Name: "reason", Type: "string"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "payment",
				Tags: []string{"stripe", "refund", "payment"}, Description: "Stripe refund request schema"},
		},
		// ── Email ──
		{
			name: "email.send",
			fields: []FieldRule{
				{Name: "to", Type: "string", Required: true, Pattern: `^[^@\s]+@[^@\s]+\.[^@\s]+$`},
				{Name: "subject", Type: "string", Required: true, MinLen: &min1, MaxLen: &max998},
				{Name: "body", Type: "string", Required: true, MinLen: &min1},
				{Name: "cc", Type: "array"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "email",
				Tags: []string{"email", "send"}, Description: "Send single email schema"},
		},
		{
			name: "email.send_bulk",
			fields: []FieldRule{
				{Name: "to", Type: "array", Required: true},
				{Name: "subject", Type: "string", Required: true, MinLen: &min1},
				{Name: "body", Type: "string", Required: true, MinLen: &min1},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "email",
				Tags: []string{"email", "bulk", "send"}, Description: "Send bulk emails schema"},
		},
		// ── GitHub ──
		{
			name: "github.create_issue",
			fields: []FieldRule{
				{Name: "owner", Type: "string", Required: true, MinLen: &min1},
				{Name: "repo", Type: "string", Required: true, MinLen: &min1},
				{Name: "title", Type: "string", Required: true, MinLen: &min1, MaxLen: &max256},
				{Name: "body", Type: "string"},
				{Name: "labels", Type: "array"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "github",
				Tags: []string{"github", "issue"}, Description: "GitHub create issue schema"},
		},
		{
			name: "github.create_pr",
			fields: []FieldRule{
				{Name: "owner", Type: "string", Required: true},
				{Name: "repo", Type: "string", Required: true},
				{Name: "title", Type: "string", Required: true, MinLen: &min1},
				{Name: "head", Type: "string", Required: true, MinLen: &min1},
				{Name: "base", Type: "string"},
				{Name: "body", Type: "string"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "github",
				Tags: []string{"github", "pr", "pull request"}, Description: "GitHub create pull request schema"},
		},
		// ── Database ──
		{
			name: "db.query",
			fields: []FieldRule{
				{Name: "query", Type: "string", Required: true, MinLen: &min1},
				{Name: "params", Type: "object"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "database",
				Tags: []string{"sql", "query", "database"}, Description: "SQL query schema with parameterized params"},
		},
		{
			name: "db.insert",
			fields: []FieldRule{
				{Name: "table", Type: "string", Required: true, MinLen: &min1, Pattern: `^[a-zA-Z_][a-zA-Z0-9_]*$`},
				{Name: "values", Type: "object", Required: true},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "database",
				Tags: []string{"sql", "insert", "database"}, Description: "SQL insert schema with table validation"},
		},
		// ── HTTP ──
		{
			name: "http.request",
			fields: []FieldRule{
				{Name: "url", Type: "string", Required: true, Pattern: `^https?://`},
				{Name: "method", Type: "string", Required: false, Pattern: `^(GET|POST|PUT|DELETE|PATCH)$`},
				{Name: "headers", Type: "object"},
				{Name: "body", Type: "object"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "http",
				Tags: []string{"http", "api", "request"}, Description: "HTTP API request schema"},
		},
		// ── File ──
		{
			name: "file.read",
			fields: []FieldRule{
				{Name: "path", Type: "string", Required: true, MinLen: &min1},
				{Name: "encoding", Type: "string"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "file",
				Tags: []string{"file", "read"}, Description: "File read schema"},
		},
		{
			name: "file.write",
			fields: []FieldRule{
				{Name: "path", Type: "string", Required: true, MinLen: &min1},
				{Name: "content", Type: "string", Required: true},
				{Name: "mode", Type: "string", Pattern: `^(w|a|x)$`},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "file",
				Tags: []string{"file", "write"}, Description: "File write schema"},
		},
		// ── Messaging ──
		{
			name: "slack.message",
			fields: []FieldRule{
				{Name: "channel", Type: "string", Required: true, MinLen: &min1},
				{Name: "text", Type: "string", Required: true, MinLen: &min1},
				{Name: "thread_ts", Type: "string"},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "messaging",
				Tags: []string{"slack", "message", "chat"}, Description: "Slack message send schema"},
		},
		// ── Project ──
		{
			name: "jira.create_ticket",
			fields: []FieldRule{
				{Name: "project", Type: "string", Required: true, MinLen: &min1, MaxLen: func() *int { v := 10; return &v }()},
				{Name: "summary", Type: "string", Required: true, MinLen: &min1},
				{Name: "description", Type: "string"},
				{Name: "issue_type", Type: "string", Pattern: `^(Bug|Task|Story|Epic)$`},
				{Name: "priority", Type: "string", Pattern: `^(Highest|High|Medium|Low|Lowest)$`},
			},
			meta: SchemaMeta{Version: "1.0.0", Author: "ark-core", Category: "project",
				Tags: []string{"jira", "ticket", "project"}, Description: "Jira create ticket schema"},
		},
	}

	for _, b := range builtins {
		h.Register(b.name, ValidationSchema{Fields: b.fields}, b.meta)
	}
}

// ─── Global Singleton ───

var globalHub *SchemaHub
var hubOnce sync.Once

// GetSchemaHub returns the global SchemaHub singleton.
func GetSchemaHub() *SchemaHub {
	hubOnce.Do(func() {
		globalHub = NewSchemaHub()
	})
	return globalHub
}

// ResetSchemaHub resets the global singleton (for testing).
func ResetSchemaHub() {
	globalHub = nil
	hubOnce = sync.Once{}
}

func orDefault(s, def string) string {
	if s == "" {
		return def
	}
	return s
}
