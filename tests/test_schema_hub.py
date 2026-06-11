"""
Tests: ARK Schema Hub — v0.4.0 Community Schema Registry
"""

import json
import os
import tempfile

from ark.schema_hub import (
    SchemaHub,
    SchemaMeta,
    get_schema_hub,
)


class TestSchemaHubBasic:
    """基础功能测试"""

    def test_init_loads_builtins(self):
        hub = SchemaHub()
        assert len(hub.available) >= 13
        assert "stripe.charge" in hub.available
        assert "email.send" in hub.available

    def test_get_builtin(self):
        hub = SchemaHub()
        schema = hub.get("stripe.charge")
        assert schema is not None

    def test_get_nonexistent(self):
        hub = SchemaHub()
        assert hub.get("nonexistent.tool") is None

    def test_available_sorted(self):
        hub = SchemaHub()
        names = hub.available
        assert names == sorted(names)


class TestSchemaMeta:
    """元数据测试"""

    def test_get_meta(self):
        hub = SchemaHub()
        meta = hub.get_meta("stripe.charge")
        assert meta is not None
        assert meta.name == "stripe.charge"
        assert meta.category == "payment"
        assert meta.version == "1.0.0"

    def test_meta_to_dict(self):
        meta = SchemaMeta(
            name="test.tool",
            version="2.0.0",
            author="alice",
            category="ai",
            tags=["openai", "llm"],
            description="A test tool",
        )
        d = meta.to_dict()
        assert d["name"] == "test.tool"
        assert d["version"] == "2.0.0"
        assert d["author"] == "alice"
        assert d["tags"] == ["openai", "llm"]

    def test_default_meta(self):
        meta = SchemaMeta(name="foo.bar")
        assert meta.version == "1.0.0"
        assert meta.author == "community"
        assert meta.category == "general"


class TestSchemaHubRegister:
    """注册测试"""

    def test_register_custom(self):
        from pydantic import BaseModel, Field

        class TestSchema(BaseModel):
            name: str = Field(min_length=1)
            age: int = Field(ge=0)

        hub = SchemaHub()
        hub.register("test.user", TestSchema, SchemaMeta(
            name="test.user",
            category="general",
            tags=["test"],
            description="Test user schema"
        ))

        assert "test.user" in hub.available
        assert hub.get("test.user") is TestSchema
        assert hub.get_meta("test.user").tags == ["test"]


class TestSchemaHubSearch:
    """搜索测试"""

    def test_search_by_category(self):
        hub = SchemaHub()
        results = hub.search(category="payment")
        names = [r.name for r in results]
        assert "stripe.charge" in names
        assert "stripe.refund" in names
        assert "email.send" not in names

    def test_search_by_tags(self):
        hub = SchemaHub()
        results = hub.search(tags=["stripe"])
        names = [r.name for r in results]
        assert "stripe.charge" in names
        assert "stripe.refund" in names

    def test_search_by_tags_and(self):
        hub = SchemaHub()
        results = hub.search(tags=["stripe", "refund"])
        names = [r.name for r in results]
        assert "stripe.refund" in names
        assert "stripe.charge" not in names  # charge doesn't have refund tag

    def test_search_by_query(self):
        hub = SchemaHub()
        results = hub.search(query="stripe")
        names = [r.name for r in results]
        assert len(names) >= 2
        assert "stripe.charge" in names

    def test_search_by_author(self):
        hub = SchemaHub()
        results = hub.search(author="ark-core")
        assert len(results) >= 13  # all builtins are ark-core

    def test_search_combined(self):
        hub = SchemaHub()
        results = hub.search(category="payment", query="stripe")
        names = [r.name for r in results]
        assert "stripe.charge" in names
        assert "stripe.refund" in names

    def test_search_no_match(self):
        hub = SchemaHub()
        results = hub.search(query="nonexistent_xyz")
        assert len(results) == 0


class TestSchemaHubCategories:
    """分类测试"""

    def test_categories(self):
        hub = SchemaHub()
        cats = hub.categories
        assert "payment" in cats
        assert "email" in cats
        assert "github" in cats

    def test_list_by_category(self):
        hub = SchemaHub()
        grouped = hub.list_by_category()
        assert "payment" in grouped
        assert len(grouped["payment"]) >= 2
        assert all(m.category == "payment" for m in grouped["payment"])


class TestSchemaHubImportExport:
    """导入导出测试"""

    # 用相对路径，兼容本地和CI环境
    SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas")

    def test_import_dir(self):
        hub = SchemaHub()
        count = hub.import_dir(self.SCHEMAS_DIR)
        assert count == 3
        assert "openai.chat_completion" in hub.available
        assert "docker.container_run" in hub.available
        assert "notion.create_page" in hub.available

    def test_imported_meta(self):
        hub = SchemaHub()
        hub.import_dir(self.SCHEMAS_DIR)
        meta = hub.get_meta("openai.chat_completion")
        assert meta.category == "ai"
        assert "openai" in meta.tags
        assert meta.author == "community"

    def test_import_nonexistent_dir(self):
        hub = SchemaHub()
        count = hub.import_dir("/nonexistent/path")
        assert count == 0

    def test_export_json(self):
        hub = SchemaHub()
        hub.import_dir(self.SCHEMAS_DIR)
        path = "/tmp/ark_schema_export_test.json"
        hub.export_json(path)
        with open(path) as f:
            data = json.load(f)
        os.unlink(path)

        assert len(data) >= 16
        names = [e["name"] for e in data]
        assert "stripe.charge" in names
        assert "openai.chat_completion" in names

    def test_export_meta_json(self):
        hub = SchemaHub()
        hub.import_dir(self.SCHEMAS_DIR)
        path = "/tmp/ark_meta_export_test.json"
        hub.export_meta_json(path)
        with open(path) as f:
            data = json.load(f)
        os.unlink(path)

        assert len(data) >= 16
        assert all("name" in e for e in data)
        assert all("category" in e for e in data)

    def test_import_empty_dir(self):
        with tempfile.TemporaryDirectory() as td:
            hub = SchemaHub()
            count = hub.import_dir(td)
            assert count == 0


class TestSchemaHubValidation:
    """验证测试"""

    SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas")

    def test_validate_valid_data(self):
        hub = SchemaHub()
        hub.import_dir(self.SCHEMAS_DIR)
        result = hub.validate("openai.chat_completion", {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hello"}],
        })
        assert result is not None
        assert result.model == "gpt-4o"

    def test_validate_missing_required(self):
        hub = SchemaHub()
        hub.import_dir(self.SCHEMAS_DIR)
        result = hub.validate("openai.chat_completion", {
            "model": "gpt-4o",
            # missing 'messages' (required)
        })
        assert result is None  # validation should fail

    def test_validate_unknown_schema(self):
        hub = SchemaHub()
        assert hub.validate("nonexistent.tool", {}) is None


class TestSchemaHubStats:
    """统计测试"""

    SCHEMAS_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas")

    def test_stats(self):
        hub = SchemaHub()
        hub.import_dir(self.SCHEMAS_DIR)
        stats = hub.stats
        assert stats["total_schemas"] >= 16
        assert "ai" in stats["by_category"]
        assert stats["by_category"]["payment"] == 2

    def test_stats_builtins_only(self):
        hub = SchemaHub()
        stats = hub.stats
        assert stats["total_schemas"] == 13


class TestSchemaHubSingleton:
    """单例测试"""

    def test_get_schema_hub_singleton(self):
        # Reset singleton for test isolation
        import ark.schema_hub as sh
        sh._hub = None

        hub1 = get_schema_hub()
        hub2 = get_schema_hub()
        assert hub1 is hub2

        sh._hub = None  # cleanup


class TestSchemaHubRepr:
    """__repr__测试"""

    def test_repr(self):
        hub = SchemaHub()
        r = repr(hub)
        assert "SchemaHub" in r
        assert "schemas=13" in r
