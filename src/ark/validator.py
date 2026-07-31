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
    """输出验证器：Agent产生的数据不合规？立即拦截

    结构守恒不变式（v0.8.2，源自 langchain-core#39152 诊断处方自审）
    ------------------------------------------------------------------
    校验 dict 输出时，未在 Schema 中声明的字段会被剔除。剔除本身是设计意图，
    「剔除而不留痕」不是。#39152 的教训是：**丢弃必须可见**。

    因此本类保证：任何被剔除的字段都会
      1. 记入 ``ValidationResult.dropped_fields``；
      2. emit ``ark.validation.dropped`` OTel 事件；
      3. 在 ``strict_extra=True`` 时直接判为契约违规（valid=False）。

    默认 ``strict_extra=False`` 以保持向后兼容——但沉默被打破了。
    """

    def __init__(self, strict_extra: bool = False):
        self.validations = 0
        self.blocked = 0
        self.passed = 0
        self.dropped = 0
        self.strict_extra = strict_extra
    
    def validate(self, schema: Type[BaseModel], output: Any, tool_name: str = "agent_output") -> "ValidationResult":
        """验证Agent输出是否符合Schema"""
        self.validations += 1
        schema_name = schema.__name__
        dropped_fields: List[str] = []
        
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
            # 对于额外字段，仅提取Schema中定义的字段。
            # 剔除是设计意图；静默剔除不是 —— 必须留痕（#39152 处方）。
            if isinstance(output, dict):
                schema_fields = set(schema.model_fields.keys())
                filtered = {k: v for k, v in output.items() if k in schema_fields}
                dropped_fields = sorted(set(output.keys()) - schema_fields)
                validated = schema(**filtered)
            else:
                validated = schema(output)

            if dropped_fields:
                self.dropped += 1
                _emit_otel(
                    "ark.validation.dropped",
                    tool_name=tool_name,
                    schema=schema_name,
                    dropped_count=len(dropped_fields),
                    dropped_fields=",".join(dropped_fields)[:200],
                )
                if self.strict_extra:
                    self.blocked += 1
                    return ValidationResult(
                        valid=False,
                        errors=[
                            "ARK: undeclared field dropped by schema filter: "
                            + ", ".join(dropped_fields)
                        ],
                        dropped_fields=dropped_fields,
                    )

            self.passed += 1
            _emit_otel(
                "ark.validation.pass",
                tool_name=tool_name,
                schema=schema_name,
            )
            return ValidationResult(
                valid=True,
                data=validated.model_dump(),
                dropped_fields=dropped_fields,
            )
        except ValidationError as e:
            self.blocked += 1
            errors = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"]) if err["loc"] else "root"
                errors.append(f"{loc}: {err['msg']} (got: {err.get('input', '?')})")
            _ = dropped_fields
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
            "dropped": self.dropped,
            "block_rate": f"{self.blocked/max(self.validations,1)*100:.1f}%",
            "drop_rate": f"{self.dropped/max(self.validations,1)*100:.1f}%",
        }


class ValidationResult:
    def __init__(
        self,
        valid: bool,
        data: Dict = None,
        errors: List[str] = None,
        dropped_fields: List[str] = None,
    ):
        self.valid = valid
        self.data = data or {}
        self.errors = errors or []
        # 结构守恒留痕：被 schema 过滤掉的字段名（#39152 处方）
        self.dropped_fields = dropped_fields or []

    def __bool__(self):
        return self.valid

    @property
    def lossless(self) -> bool:
        """True 表示本次校验没有丢弃任何字段（结构守恒）。"""
        return not self.dropped_fields

    def to_dict(self):
        return {
            "valid": self.valid,
            "data": self.data,
            "errors": self.errors,
            "dropped_fields": self.dropped_fields,
        }
