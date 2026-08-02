package ark

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

// ─── 1. Registration & Discovery ───

func TestSchemaHub_RegisterAndGet(t *testing.T) {
	h := NewSchemaHub()

	schema, ok := h.Get("stripe.charge")
	if !ok {
		t.Fatal("stripe.charge not found in builtins")
	}
	if len(schema.Fields) != 4 {
		t.Fatalf("expected 4 fields, got %d", len(schema.Fields))
	}

	meta, ok := h.GetMeta("stripe.charge")
	if !ok {
		t.Fatal("stripe.charge meta not found")
	}
	if meta.Category != "payment" {
		t.Fatalf("expected category payment, got %s", meta.Category)
	}
	if meta.Version != "1.0.0" {
		t.Fatalf("expected version 1.0.0, got %s", meta.Version)
	}
}

func TestSchemaHub_Available(t *testing.T) {
	h := NewSchemaHub()
	names := h.Available()
	if len(names) != 13 {
		t.Fatalf("expected 13 builtin schemas, got %d: %v", len(names), names)
	}
}

func TestSchemaHub_Categories(t *testing.T) {
	h := NewSchemaHub()
	cats := h.Categories()
	// Should have: database, email, file, github, http, messaging, payment, project
	if len(cats) < 7 {
		t.Fatalf("expected >=7 categories, got %d: %v", len(cats), cats)
	}
}

// ─── 2. Search ───

func TestSchemaHub_SearchByCategory(t *testing.T) {
	h := NewSchemaHub()
	results := h.Search("", "github", nil, "")
	if len(results) != 2 {
		t.Fatalf("expected 2 github schemas, got %d", len(results))
	}
	for _, r := range results {
		if r.Category != "github" {
			t.Errorf("expected github category, got %s", r.Category)
		}
	}
}

func TestSchemaHub_SearchByTags(t *testing.T) {
	h := NewSchemaHub()
	results := h.Search("", "", []string{"stripe"}, "")
	if len(results) != 2 {
		t.Fatalf("expected 2 stripe-tagged schemas, got %d", len(results))
	}
}

func TestSchemaHub_SearchByQuery(t *testing.T) {
	h := NewSchemaHub()
	results := h.Search("charge", "", nil, "")
	if len(results) < 1 {
		t.Fatal("expected at least 1 'charge' match")
	}
	found := false
	for _, r := range results {
		if r.Name == "stripe.charge" {
			found = true
		}
	}
	if !found {
		t.Error("stripe.charge not found by query 'charge'")
	}
}

func TestSchemaHub_SearchByAuthor(t *testing.T) {
	h := NewSchemaHub()
	results := h.Search("", "", nil, "ark-core")
	if len(results) != 13 {
		t.Fatalf("expected 13 ark-core schemas, got %d", len(results))
	}
}

func TestSchemaHub_SearchCombined(t *testing.T) {
	h := NewSchemaHub()
	// payment category + stripe tag + ark-core author
	results := h.Search("", "payment", []string{"stripe"}, "ark-core")
	if len(results) != 2 {
		t.Fatalf("expected 2 combined hits, got %d", len(results))
	}
}

func TestSchemaHub_SearchNoMatch(t *testing.T) {
	h := NewSchemaHub()
	results := h.Search("nonexistent_schema_xyz", "", nil, "")
	if len(results) != 0 {
		t.Fatalf("expected 0 results, got %d", len(results))
	}
}

// ─── 3. ListByCategory ───

func TestSchemaHub_ListByCategory(t *testing.T) {
	h := NewSchemaHub()
	byCat := h.ListByCategory()

	if len(byCat["payment"]) != 2 {
		t.Errorf("expected 2 payment schemas, got %d", len(byCat["payment"]))
	}
	if len(byCat["email"]) != 2 {
		t.Errorf("expected 2 email schemas, got %d", len(byCat["email"]))
	}
	if len(byCat["messaging"]) != 1 {
		t.Errorf("expected 1 messaging schema, got %d", len(byCat["messaging"]))
	}
}

// ─── 4. Validate ───

func TestSchemaHub_ValidatePass(t *testing.T) {
	h := NewSchemaHub()

	result, err := h.Validate("stripe.charge", map[string]interface{}{
		"amount":   99.99,
		"currency": "usd",
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !result.Passed {
		t.Fatalf("expected pass, got errors: %+v", result.Errors)
	}
}

func TestSchemaHub_ValidateFail(t *testing.T) {
	h := NewSchemaHub()

	result, err := h.Validate("stripe.charge", map[string]interface{}{
		"amount": -5.0, // negative → fails Min > 0
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Passed {
		t.Fatal("expected fail for negative amount")
	}
}

func TestSchemaHub_ValidateMissingRequired(t *testing.T) {
	h := NewSchemaHub()

	result, err := h.Validate("email.send", map[string]interface{}{
		"subject": "Hello",
		// missing "to" (required) and "body" (required)
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Passed {
		t.Fatal("expected fail for missing required fields")
	}
}

func TestSchemaHub_ValidatePatternFail(t *testing.T) {
	h := NewSchemaHub()

	result, err := h.Validate("http.request", map[string]interface{}{
		"url": "ftp://invalid.com", // not http/https
	})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if result.Passed {
		t.Fatal("expected fail for ftp URL")
	}
}

func TestSchemaHub_ValidateUnknownSchema(t *testing.T) {
	h := NewSchemaHub()

	_, err := h.Validate("nonexistent.schema", map[string]interface{}{})
	if err == nil {
		t.Fatal("expected error for unknown schema")
	}
}

// ─── 5. Stats ───

func TestSchemaHub_Stats(t *testing.T) {
	h := NewSchemaHub()
	s := h.Stats()

	total, ok := s["total_schemas"].(int)
	if !ok || total != 13 {
		t.Errorf("expected 13 total_schemas, got %v", s["total_schemas"])
	}
	cats, ok := s["categories"].(int)
	if !ok || cats < 7 {
		t.Errorf("expected >=7 categories, got %v", s["categories"])
	}
	byCat, ok := s["by_category"].(map[string]int)
	if !ok {
		t.Error("by_category should be map[string]int")
	}
	if byCat["payment"] != 2 {
		t.Errorf("expected 2 payment in by_category, got %d", byCat["payment"])
	}
}

// ─── 6. Import / Export ───

func TestSchemaHub_ExportImportMetaJSON(t *testing.T) {
	h := NewSchemaHub()

	tmpDir := t.TempDir()
	metaPath := filepath.Join(tmpDir, "meta.json")

	if err := h.ExportMetaJSON(metaPath); err != nil {
		t.Fatalf("export failed: %v", err)
	}

	data, err := os.ReadFile(metaPath)
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}

	var metas []SchemaMeta
	if err := json.Unmarshal(data, &metas); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if len(metas) != 13 {
		t.Fatalf("expected 13 metas in export, got %d", len(metas))
	}
}

func TestSchemaHub_ExportJSON(t *testing.T) {
	h := NewSchemaHub()

	tmpDir := t.TempDir()
	exportPath := filepath.Join(tmpDir, "schemas.json")

	if err := h.ExportJSON(exportPath); err != nil {
		t.Fatalf("export failed: %v", err)
	}

	data, err := os.ReadFile(exportPath)
	if err != nil {
		t.Fatalf("read failed: %v", err)
	}

	var entries []exportEntry
	if err := json.Unmarshal(data, &entries); err != nil {
		t.Fatalf("unmarshal failed: %v", err)
	}
	if len(entries) != 13 {
		t.Fatalf("expected 13 entries, got %d", len(entries))
	}
}

func TestSchemaHub_ImportDir(t *testing.T) {
	h := NewSchemaHub()

	tmpDir := t.TempDir()
	customPath := filepath.Join(tmpDir, "custom_tool.json")
	customJSON := `{
		"name": "custom.tool",
		"version": "2.0.0",
		"author": "test-user",
		"category": "ai",
		"tags": ["openai", "chat"],
		"description": "A custom AI tool schema",
		"fields": [
			{"name": "prompt", "type": "string", "required": true},
			{"name": "temperature", "type": "number"}
		]
	}`
	if err := os.WriteFile(customPath, []byte(customJSON), 0644); err != nil {
		t.Fatalf("write custom schema failed: %v", err)
	}

	count := h.ImportDir(tmpDir)
	if count != 1 {
		t.Fatalf("expected 1 imported schema, got %d", count)
	}

	schema, ok := h.Get("custom.tool")
	if !ok {
		t.Fatal("custom.tool not found after import")
	}
	if len(schema.Fields) != 2 {
		t.Fatalf("expected 2 fields, got %d", len(schema.Fields))
	}

	meta, ok := h.GetMeta("custom.tool")
	if !ok {
		t.Fatal("custom.tool meta not found")
	}
	if meta.Category != "ai" {
		t.Fatalf("expected category ai, got %s", meta.Category)
	}
	if meta.Author != "test-user" {
		t.Fatalf("expected author test-user, got %s", meta.Author)
	}
	if meta.Version != "2.0.0" {
		t.Fatalf("expected version 2.0.0, got %s", meta.Version)
	}
	if len(meta.Tags) != 2 {
		t.Fatalf("expected 2 tags, got %d", len(meta.Tags))
	}
}

func TestSchemaHub_ImportDir_InvalidJSON(t *testing.T) {
	h := NewSchemaHub()

	tmpDir := t.TempDir()
	badPath := filepath.Join(tmpDir, "bad.json")
	if err := os.WriteFile(badPath, []byte(`{not valid json`), 0644); err != nil {
		t.Fatalf("write failed: %v", err)
	}

	count := h.ImportDir(tmpDir)
	if count != 0 {
		t.Fatalf("expected 0 imports from bad JSON, got %d", count)
	}
}

func TestSchemaHub_ImportDir_EmptyName(t *testing.T) {
	h := NewSchemaHub()

	tmpDir := t.TempDir()
	emptyPath := filepath.Join(tmpDir, "empty.json")
	if err := os.WriteFile(emptyPath, []byte(`{"name":"","fields":[]}`), 0644); err != nil {
		t.Fatalf("write failed: %v", err)
	}

	count := h.ImportDir(tmpDir)
	if count != 0 {
		t.Fatalf("expected 0 imports from empty-name schema, got %d", count)
	}
}

// ─── 7. Global Singleton ───

func TestGetSchemaHub(t *testing.T) {
	ResetSchemaHub()
	h1 := GetSchemaHub()
	h2 := GetSchemaHub()
	if h1 != h2 {
		t.Fatal("GetSchemaHub should return the same instance")
	}
	if len(h1.Available()) != 13 {
		t.Fatalf("expected 13 builtins, got %d", len(h1.Available()))
	}
}

// ─── 8. Validate edge cases ───

func TestSchemaHub_ValidateAll13Builtins(t *testing.T) {
	h := NewSchemaHub()

	tests := []struct {
		name string
		data map[string]interface{}
		pass bool
	}{
		{"stripe.charge", map[string]interface{}{"amount": 50.0, "currency": "eur"}, true},
		{"stripe.refund", map[string]interface{}{"charge_id": "ch_12345"}, true},
		{"email.send", map[string]interface{}{
			"to": "user@example.com", "subject": "Hello", "body": "World",
		}, true},
		{"email.send_bulk", map[string]interface{}{
			"to": []interface{}{"a@b.com"}, "subject": "Hi", "body": "Msg",
		}, true},
		{"github.create_issue", map[string]interface{}{
			"owner": "test", "repo": "test", "title": "Bug",
		}, true},
		{"github.create_pr", map[string]interface{}{
			"owner": "test", "repo": "test", "title": "Fix", "head": "feature",
		}, true},
		{"db.query", map[string]interface{}{"query": "SELECT 1"}, true},
		{"db.insert", map[string]interface{}{
			"table": "users", "values": map[string]interface{}{"name": "Alice"},
		}, true},
		{"http.request", map[string]interface{}{
			"url": "https://api.example.com", "method": "GET",
		}, true},
		{"file.read", map[string]interface{}{"path": "/tmp/test.txt"}, true},
		{"file.write", map[string]interface{}{
			"path": "/tmp/test.txt", "content": "data",
		}, true},
		{"slack.message", map[string]interface{}{
			"channel": "general", "text": "Hello",
		}, true},
		{"jira.create_ticket", map[string]interface{}{
			"project": "ARK", "summary": "Fix bug",
		}, true},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			result, err := h.Validate(tt.name, tt.data)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if result.Passed != tt.pass {
				t.Errorf("expected pass=%v, got pass=%v, errors=%+v", tt.pass, result.Passed, result.Errors)
			}
		})
	}
}

func TestSchemaHub_ValidateEmailInvalidFormat(t *testing.T) {
	h := NewSchemaHub()

	result, err := h.Validate("email.send", map[string]interface{}{
		"to":      "not-an-email",
		"subject": "Hi",
		"body":    "Test",
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Passed {
		t.Fatal("expected fail for invalid email format")
	}
}

func TestSchemaHub_ValidateJiraInvalidIssueType(t *testing.T) {
	h := NewSchemaHub()

	result, err := h.Validate("jira.create_ticket", map[string]interface{}{
		"project":    "ARK",
		"summary":    "Fix",
		"issue_type": "Invalid",
	})
	if err != nil {
		t.Fatal(err)
	}
	if result.Passed {
		t.Fatal("expected fail for invalid issue_type")
	}
}
