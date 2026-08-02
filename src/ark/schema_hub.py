"""
ARK Schema Hub — Community Schema Registry
v0.4.0: 社区驱动的Schema生态中心

设计哲学:
  1. 零摩擦贡献 — 一个Python文件即一个Schema
  2. 离线/在线双模 — 本地缓存 + 远程Hub
  3. 版本化 — 每个Schema带语义化版本
  4. 可发现 — 按类别、标签、评分搜索
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, Field


@dataclass
class SchemaMeta:
    """Schema元数据"""
    name: str
    version: str = "1.0.0"
    author: str = "community"
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    description: str = ""
    source: str = "local"  # local | remote
    downloads: int = 0
    rating: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "category": self.category,
            "tags": self.tags,
            "description": self.description,
            "source": self.source,
            "downloads": self.downloads,
            "rating": self.rating,
        }


# ─── 内置类别 ───
CATEGORIES = [
    "payment",     # 支付
    "email",       # 邮件
    "github",      # GitHub
    "database",    # 数据库
    "http",        # HTTP/API
    "file",        # 文件操作
    "messaging",   # 消息
    "project",     # 项目管理
    "ai",          # AI/ML
    "security",    # 安全
    "general",     # 通用
]


class SchemaHub:
    """
    Community Schema Hub — 社区驱动的Schema注册与发现中心

    用法:
        hub = SchemaHub()
        hub.register(my_schema)  # 注册本地Schema
        hub.import_dir("./schemas")  # 批量加载
        results = hub.search(category="payment")  # 按类别搜索
        results = hub.search(tags=["stripe", "refund"])  # 按标签搜索
        hub.export_json("schemas.json")  # 导出供他人使用
    """

    def __init__(self, schemas_dir: Optional[str] = None):
        self._schemas: Dict[str, Type[BaseModel]] = {}
        self._meta: Dict[str, SchemaMeta] = {}
        self._schemas_dir = Path(schemas_dir) if schemas_dir else None
        self._register_builtins()

    # ═══════════════════════════════════════════════
    # Registration
    # ═══════════════════════════════════════════════

    def register(
        self,
        name: str,
        schema_cls: Type[BaseModel],
        meta: Optional[SchemaMeta] = None,
    ) -> None:
        """注册一个Schema到Hub"""
        self._schemas[name] = schema_cls
        if meta is None:
            meta = SchemaMeta(name=name)
        self._meta[name] = meta

    def _register_builtins(self) -> None:
        """注册13个内置Schema"""

        # === 支付 ===
        class StripeCharge(BaseModel):
            amount: float = Field(gt=0, description="Charge amount in cents")
            currency: str = Field(default="usd", pattern=r"^[a-z]{3}$")
            description: Optional[str] = Field(default=None)
            customer: Optional[str] = Field(default=None)

        class StripeRefund(BaseModel):
            charge_id: str = Field(min_length=5)
            amount: Optional[float] = Field(default=None, gt=0)
            reason: Optional[str] = Field(default=None)

        # === 邮件 ===
        class SendEmail(BaseModel):
            to: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
            subject: str = Field(min_length=1, max_length=998)
            body: str = Field(min_length=1)
            cc: Optional[List[str]] = Field(default=None)

        class SendBulkEmail(BaseModel):
            to: List[str] = Field(min_length=1)
            subject: str = Field(min_length=1)
            body: str = Field(min_length=1)

        # === GitHub ===
        class GitHubCreateIssue(BaseModel):
            owner: str = Field(min_length=1)
            repo: str = Field(min_length=1)
            title: str = Field(min_length=1, max_length=256)
            body: Optional[str] = Field(default="")
            labels: Optional[List[str]] = Field(default=None)

        class GitHubCreatePR(BaseModel):
            owner: str
            repo: str
            title: str = Field(min_length=1)
            head: str = Field(min_length=1)
            base: str = Field(default="main")
            body: Optional[str] = Field(default="")

        # === 数据库 ===
        class SQLQuery(BaseModel):
            query: str = Field(min_length=1)
            params: Optional[Dict] = Field(default=None)

        class SQLInsert(BaseModel):
            table: str = Field(min_length=1, pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")
            values: Dict = Field(min_length=1)

        # === HTTP ===
        class HTTPRequest(BaseModel):
            url: str = Field(pattern=r"^https?://")
            method: str = Field(default="GET", pattern=r"^(GET|POST|PUT|DELETE|PATCH)$")
            headers: Optional[Dict] = Field(default=None)
            body: Optional[Dict] = Field(default=None)

        # === 文件 ===
        class FileRead(BaseModel):
            path: str = Field(min_length=1)
            encoding: str = Field(default="utf-8")

        class FileWrite(BaseModel):
            path: str = Field(min_length=1)
            content: str
            mode: str = Field(default="w", pattern=r"^(w|a|x)$")

        # === Slack ===
        class SlackMessage(BaseModel):
            channel: str = Field(min_length=1)
            text: str = Field(min_length=1)
            thread_ts: Optional[str] = Field(default=None)

        # === Jira ===
        class JiraCreateTicket(BaseModel):
            project: str = Field(min_length=1, max_length=10)
            summary: str = Field(min_length=1)
            description: Optional[str] = Field(default="")
            issue_type: str = Field(default="Bug", pattern=r"^(Bug|Task|Story|Epic)$")
            priority: str = Field(default="Medium", pattern=r"^(Highest|High|Medium|Low|Lowest)$")

        # 注册内置Schema + 元数据
        builtins: Dict[str, tuple[Type[BaseModel], SchemaMeta]] = {
            "stripe.charge": (StripeCharge, SchemaMeta(
                name="stripe.charge", version="1.0.0", author="ark-core",
                category="payment", tags=["stripe", "charge", "payment"],
                description="Stripe charge request schema"
            )),
            "stripe.refund": (StripeRefund, SchemaMeta(
                name="stripe.refund", version="1.0.0", author="ark-core",
                category="payment", tags=["stripe", "refund", "payment"],
                description="Stripe refund request schema"
            )),
            "email.send": (SendEmail, SchemaMeta(
                name="email.send", version="1.0.0", author="ark-core",
                category="email", tags=["email", "send"],
                description="Send single email schema"
            )),
            "email.send_bulk": (SendBulkEmail, SchemaMeta(
                name="email.send_bulk", version="1.0.0", author="ark-core",
                category="email", tags=["email", "bulk", "send"],
                description="Send bulk emails schema"
            )),
            "github.create_issue": (GitHubCreateIssue, SchemaMeta(
                name="github.create_issue", version="1.0.0", author="ark-core",
                category="github", tags=["github", "issue"],
                description="GitHub create issue schema"
            )),
            "github.create_pr": (GitHubCreatePR, SchemaMeta(
                name="github.create_pr", version="1.0.0", author="ark-core",
                category="github", tags=["github", "pr", "pull request"],
                description="GitHub create pull request schema"
            )),
            "db.query": (SQLQuery, SchemaMeta(
                name="db.query", version="1.0.0", author="ark-core",
                category="database", tags=["sql", "query", "database"],
                description="SQL query schema with parameterized params"
            )),
            "db.insert": (SQLInsert, SchemaMeta(
                name="db.insert", version="1.0.0", author="ark-core",
                category="database", tags=["sql", "insert", "database"],
                description="SQL insert schema with table validation"
            )),
            "http.request": (HTTPRequest, SchemaMeta(
                name="http.request", version="1.0.0", author="ark-core",
                category="http", tags=["http", "api", "request"],
                description="HTTP API request schema"
            )),
            "file.read": (FileRead, SchemaMeta(
                name="file.read", version="1.0.0", author="ark-core",
                category="file", tags=["file", "read"],
                description="File read schema"
            )),
            "file.write": (FileWrite, SchemaMeta(
                name="file.write", version="1.0.0", author="ark-core",
                category="file", tags=["file", "write"],
                description="File write schema"
            )),
            "slack.message": (SlackMessage, SchemaMeta(
                name="slack.message", version="1.0.0", author="ark-core",
                category="messaging", tags=["slack", "message", "chat"],
                description="Slack message send schema"
            )),
            "jira.create_ticket": (JiraCreateTicket, SchemaMeta(
                name="jira.create_ticket", version="1.0.0", author="ark-core",
                category="project", tags=["jira", "ticket", "project"],
                description="Jira create ticket schema"
            )),
        }

        for name, (cls, meta) in builtins.items():
            self.register(name, cls, meta)

    # ═══════════════════════════════════════════════
    # Discovery
    # ═══════════════════════════════════════════════

    def get(self, name: str) -> Optional[Type[BaseModel]]:
        """获取单个Schema"""
        return self._schemas.get(name)

    def get_meta(self, name: str) -> Optional[SchemaMeta]:
        """获取Schema元数据"""
        return self._meta.get(name)

    @property
    def available(self) -> List[str]:
        """所有已注册Schema名称"""
        return sorted(self._schemas.keys())

    @property
    def categories(self) -> List[str]:
        """所有类别"""
        seen = set()
        for m in self._meta.values():
            seen.add(m.category)
        return sorted(seen)

    def search(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        author: Optional[str] = None,
    ) -> List[SchemaMeta]:
        """
        多维度搜索Schema

        Args:
            query: 名称/描述中包含的文字
            category: 按类别过滤
            tags: 按标签过滤 (AND逻辑)
            author: 按作者过滤

        Returns:
            匹配的SchemaMeta列表
        """
        results = []
        for name, meta in self._meta.items():
            # query 匹配
            if query and query.lower() not in name.lower() and query.lower() not in meta.description.lower():
                continue
            # category 过滤
            if category and meta.category != category:
                continue
            # tags 过滤 (AND)
            if tags and not all(t in meta.tags for t in tags):
                continue
            # author 过滤
            if author and meta.author != author:
                continue
            results.append(meta)
        return results

    def list_by_category(self) -> Dict[str, List[SchemaMeta]]:
        """按类别分组列出所有Schema"""
        result: Dict[str, List[SchemaMeta]] = {}
        for meta in self._meta.values():
            result.setdefault(meta.category, []).append(meta)
        return result

    # ═══════════════════════════════════════════════
    # Import / Export
    # ═══════════════════════════════════════════════

    def import_dir(self, dir_path: str) -> int:
        """
        从目录批量加载Schema JSON文件

        Schema JSON格式:
        {
            "name": "tool_name",
            "version": "1.0.0",
            "author": "community_user",
            "category": "ai",
            "tags": ["openai", "chat"],
            "description": "...",
            "fields": {
                "field_name": {"type": "str", "required": true, "description": "..."},
                ...
            }
        }

        返回加载数量
        """
        import json as json_module
        from pydantic import create_model

        d = Path(dir_path)
        if not d.is_dir():
            return 0

        count = 0
        for f in d.glob("*.json"):
            try:
                data = json_module.loads(f.read_text())
                fields_data = data.get("fields", {})
                fields = {}
                for fname, finfo in fields_data.items():
                    t = finfo.get("type", "str")
                    required = finfo.get("required", True)
                    desc = finfo.get("description", "")
                    if t == "str":
                        fields[fname] = (str, Field(default=... if required else None, description=desc))
                    elif t == "int":
                        fields[fname] = (int, Field(default=... if required else None, description=desc))
                    elif t == "float":
                        fields[fname] = (float, Field(default=... if required else None, description=desc))
                    elif t == "bool":
                        fields[fname] = (bool, Field(default=... if required else None, description=desc))
                    elif t.startswith("list["):
                        fields[fname] = (List, Field(default=... if required else None, description=desc))
                    elif t.startswith("dict"):
                        fields[fname] = (Dict, Field(default=... if required else None, description=desc))
                    else:
                        fields[fname] = (Optional[str], Field(default=None, description=desc))

                if fields:
                    model = create_model(data["name"].replace(".", "_"), **fields)
                    meta = SchemaMeta(
                        name=data["name"],
                        version=data.get("version", "1.0.0"),
                        author=data.get("author", "community"),
                        category=data.get("category", "general"),
                        tags=data.get("tags", []),
                        description=data.get("description", ""),
                        source="local",
                    )
                    self.register(data["name"], model, meta)
                    count += 1
            except Exception:
                continue

        return count

    def export_json(self, path: str) -> None:
        """导出所有Schema为JSON (供社区导入)"""
        result = []
        for name, schema_cls in self._schemas.items():
            meta = self._meta.get(name)
            entry = {
                "name": name,
                "version": meta.version if meta else "1.0.0",
                "author": meta.author if meta else "community",
                "category": meta.category if meta else "general",
                "tags": meta.tags if meta else [],
                "description": meta.description if meta else "",
                "json_schema": schema_cls.model_json_schema(),
            }
            result.append(entry)
        with open(path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    def export_meta_json(self, path: str) -> None:
        """导出所有元数据为JSON (轻量版，供搜索索引)"""
        result = [m.to_dict() for m in self._meta.values()]
        with open(path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    # ═══════════════════════════════════════════════
    # Validation
    # ═══════════════════════════════════════════════

    def validate(self, name: str, data: Any) -> Optional[BaseModel]:
        """使用Hub中的Schema验证数据"""
        schema = self.get(name)
        if schema is None:
            return None
        try:
            return schema(**data) if isinstance(data, dict) else schema.model_validate(data)
        except Exception:
            return None

    # ═══════════════════════════════════════════════
    # Stats
    # ═══════════════════════════════════════════════

    @property
    def stats(self) -> Dict[str, Any]:
        """Hub统计信息"""
        cats = self.list_by_category()
        return {
            "total_schemas": len(self._schemas),
            "categories": len(cats),
            "by_category": {k: len(v) for k, v in cats.items()},
            "total_tags": len(set(t for m in self._meta.values() for t in m.tags)),
            "authors": len(set(m.author for m in self._meta.values())),
        }

    def __repr__(self) -> str:
        return f"SchemaHub(schemas={len(self._schemas)}, categories={len(self.categories)})"


# ─── 全局单例 ───
_hub: Optional[SchemaHub] = None


def get_schema_hub(schemas_dir: Optional[str] = None) -> SchemaHub:
    """获取全局SchemaHub单例"""
    global _hub
    if _hub is None:
        _hub = SchemaHub(schemas_dir=schemas_dir)
    return _hub
