"""
ARK 集成测试
"""
import pytest, time, json
import sys
sys.path.insert(0, '/Users/w/.hermes/projects/ark/src')

from ark import IdempotencyGuard, CircuitBreaker, OutputValidator, Trace
from pydantic import BaseModel

class TestIdempotencyGuard:
    def test_intercept_duplicate(self):
        g = IdempotencyGuard()
        call_count = [0]
        
        @g.wrap
        def test_tool(x: int):
            call_count[0] += 1
            return x * 2
        
        assert test_tool(5) == 10
        assert test_tool(5) == 10  # 幂等拦截
        assert call_count[0] == 1
        
    def test_different_args_pass(self):
        g = IdempotencyGuard()
        
        @g.wrap
        def echo(msg: str):
            return msg
        
        assert echo(msg="hello") == "hello"
        assert echo(msg="world") == "world"  # 不同参数→通过
        assert g.stats['passes'] == 2
    
    def test_stats(self):
        g = IdempotencyGuard()
        
        @g.wrap
        def f(x): return x
        
        f(x=1); f(x=1); f(x=1)
        s = g.stats
        assert s['intercepts'] == 2
        assert s['passes'] == 1


class TestCircuitBreaker:
    def test_opens_after_failures(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        calls = 0
        
        for _ in range(3):
            try:
                cb.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except:
                calls += 1
        
        assert cb.state == "open"
    
    def test_fallback_works(self):
        cb = CircuitBreaker("test", failure_threshold=1)
        
        result = cb.call(
            lambda: (_ for _ in ()).throw(Exception("fail")),
            fallback=lambda: "safe"
        )
        assert result == "safe"


class TestOutputValidator:
    def test_valid_output(self):
        class User(BaseModel):
            name: str
            age: int
        
        v = OutputValidator()
        r = v.validate(User, {"name": "Alice", "age": 30})
        assert r.valid
        assert r.data["name"] == "Alice"
    
    def test_invalid_output(self):
        from pydantic import Field
        class Payment(BaseModel):
            amount: float = Field(gt=0)
        
        v = OutputValidator()
        r = v.validate(Payment, {"amount": -1})
        assert not r.valid
        assert len(r.errors) > 0
    
    def test_none_output(self):
        class Any(BaseModel):
            pass
        
        v = OutputValidator()
        r = v.validate(Any, None)
        assert not r.valid


class TestTrace:
    def test_tree(self):
        t = Trace("test")
        t.start_span("A")
        t.end_span()
        t.start_span("B")
        t.end_span()
        
        s = t.summary()
        assert s["total_spans"] == 3
        assert s["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
