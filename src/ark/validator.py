"""
ARK 输出验证器 — IDE基因移植
Agent输出实时类型检查+Schema验证
"""

from typing import Any, Dict, List, Type, get_type_hints
from pydantic import BaseModel, ValidationError

class OutputValidator:
    """输出验证器：Agent产生的数据不合规？立即拦截"""
    
    def __init__(self):
        self.validations = 0
        self.blocked = 0
        self.passed = 0
    
    def validate(self, schema: Type[BaseModel], output: Any) -> "ValidationResult":
        """验证Agent输出是否符合Schema"""
        self.validations += 1
        
        if output is None:
            self.blocked += 1
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
            validated = schema(**output) if isinstance(output, dict) else schema(output)
            self.passed += 1
            return ValidationResult(valid=True, data=validated.model_dump())
        except ValidationError as e:
            self.blocked += 1
            errors = []
            for err in e.errors():
                loc = ".".join(str(x) for x in err["loc"]) if err["loc"] else "root"
                errors.append(f"{loc}: {err['msg']} (got: {err.get('input', '?')})")
            return ValidationResult(valid=False, errors=errors)
        except Exception as e:
            self.blocked += 1
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
