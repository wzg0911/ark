"""
ARK Schema Registry — 社区贡献的工具Schema库
开箱即用的Pydantic Schema，覆盖主流API
"""

from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field


class SchemaRegistry:
    """社区驱动的工具Schema库"""
    
    def __init__(self):
        self._schemas: Dict[str, Type[BaseModel]] = {}
        self._register_builtins()
    
    def _register_builtins(self):
        """注册内置Schema — 覆盖最常见工具"""
        
        # === 支付 (Stripe基因) ===
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
        
        # === HTTP API ===
        class HTTPRequest(BaseModel):
            url: str = Field(pattern=r"^https?://")
            method: str = Field(default="GET", pattern=r"^(GET|POST|PUT|DELETE|PATCH)$")
            headers: Optional[Dict] = Field(default=None)
            body: Optional[Dict] = Field(default=None)
        
        # === 文件操作 ===
        class FileRead(BaseModel):
            path: str = Field(min_length=1)
            encoding: str = Field(default="utf-8")
        
        class FileWrite(BaseModel):
            path: str = Field(min_length=1)
            content: str
            mode: str = Field(default="w", pattern=r"^(w|a|x)$")
        
        # === Slack / 消息 ===
        class SlackMessage(BaseModel):
            channel: str = Field(min_length=1)
            text: str = Field(min_length=1)
            thread_ts: Optional[str] = Field(default=None)
        
        # === Jira / 项目管理 ===
        class JiraCreateTicket(BaseModel):
            project: str = Field(min_length=1, max_length=10)
            summary: str = Field(min_length=1)
            description: Optional[str] = Field(default="")
            issue_type: str = Field(default="Bug", pattern=r"^(Bug|Task|Story|Epic)$")
            priority: str = Field(default="Medium", pattern=r"^(Highest|High|Medium|Low|Lowest)$")
        
        # Register all
        builtins = {
            "stripe.charge": StripeCharge,
            "stripe.refund": StripeRefund,
            "email.send": SendEmail,
            "email.send_bulk": SendBulkEmail,
            "github.create_issue": GitHubCreateIssue,
            "github.create_pr": GitHubCreatePR,
            "db.query": SQLQuery,
            "db.insert": SQLInsert,
            "http.request": HTTPRequest,
            "file.read": FileRead,
            "file.write": FileWrite,
            "slack.message": SlackMessage,
            "jira.create_ticket": JiraCreateTicket,
        }
        self._schemas.update(builtins)
    
    @property
    def available(self) -> List[str]:
        return sorted(self._schemas.keys())
    
    def get(self, tool_name: str) -> Optional[Type[BaseModel]]:
        return self._schemas.get(tool_name)
    
    def register(self, tool_name: str, schema: Type[BaseModel]):
        """注册自定义Schema"""
        self._schemas[tool_name] = schema
    
    def validate(self, tool_name: str, output: Any, validator=None):
        """使用注册的Schema验证输出"""
        schema = self.get(tool_name)
        if not schema:
            return None
        if validator is None:
            from .validator import OutputValidator
            validator = OutputValidator()
        return validator.validate(schema, output)
    
    def export(self) -> Dict:
        """导出所有Schema为JSON Schema格式"""
        return {name: schema.model_json_schema() for name, schema in self._schemas.items()}
