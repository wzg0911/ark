"""
ARK 输出验证器 — IDE基因移植
Agent输出实时类型检查+Schema验证
"""

import os
from typing import Any, Dict, List, Type, get_type_hints
from pydantic import BaseModel, ValidationError

# OTel 集成：函数内读取env，确保"运行时激活"生效


def _emit_otel(event_type: str, tool_name: str, **attrs):
    """内部 helper：OTel 关闭时 zero overhead"""
    if not os.getenv("ARK_OTEL_ENDPOINT", ""):
        return
    try:
        from .otel_exporter import get_otel_exporter, EventType
        et = EventType(event_type)
        get_otel_exporter().emit(et, tool_name=tool_name, attributes=attrs)
    except Exception:
        pass


class OutputValidator:
    """输出验证器：Agent产生的数据不合规？立即拦截"""
    
    def __init__(self):
        self.validations = 0
        self.blocked = 0
        self.passed = 0
    
    def validate(self, schema: Type[BaseModel], output: Any, tool_name: str = "agent_output") -> "ValidationResult":
        """验证Agent输出是否符合Schema"""
        self.validations += 1
        schema_name = schema.__name__
        
        if output is None:
            self.blocked += 1
            _emit_otel(
                "ark.validation.fail",
                tool_name=tool_name,
                schema=schema_name,
                reason="null_output",
            )
            return ValidationResult(
                valid=False,
                errors=["ARK: Agent returned None/null"]
            )
        
        if isinstance(output, str):
            try:
                import json
                output = json.loads(output)
            except:
                pass
        
        try:
            # 对于额外字段，仅提取Schema中定义的字段，忽略未定义的
            if isinstance(output, dict):
                schema_fields = set(schema.model_fields.keys())
                filtered = {k: v for k, v in output.items() if k in schema_fields}
                validated = schema(**filtered)
            else:
                validated = schema(output)
            self.passed += 1
            _emit_otel(
                "ark.validation.pass",
                tool_name=tool_name,
                schema=schema_name,
            )
            return ValidationResult(valid=True, data=validated.model_dump())
        except ValidationError as e:
            self.blocked += 1
            errors = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"]) if err["loc"] else "root"
                errors.append(f"{loc}: {err['msg']} (got: {err.get('input', '?')})")
            _emit_otel(
                "ark.validation.fail",
                tool_name=tool_name,
                schema=schema_name,
                error_count=len(errors),
                first_error=errors[0][:200] if errors else "",
            )
            return ValidationResult(valid=False, errors=errors)
        except Exception as e:
            self.blocked += 1
            _emit_otel(
                "ark.validation.fail",
                tool_name=tool_name,
                schema=schema_name,
                reason="exception",
                error=str(e)[:200],
            )
            return ValidationResult(valid=False, errors=[f"Validation error: {str(e)}"])
    
    @property
    def stats(self) -> Dict:
        return {
            "validations": self.validations,
            "passed": self.passed,
            "blocked": self.blocked,
            "block_rate": f"{self.blocked/max(self.validations,1)*100:.1f}%"
        }


class ValidationResult:
    def __init__(self, valid: bool, data: Dict = None, errors: List[str] = None):
        self.valid = valid
        self.data = data or {}
        self.errors = errors or []
    
    def __bool__(self):
        return self.valid
    
    def to_dict(self):
        return {
            "valid": self.valid,
            "data": self.data,
            "errors": self.errors
        }
