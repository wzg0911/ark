"""
ARK Benchmarks — v0.4.0
Performance benchmark suite for core ARK components.

用法:
    python -m ark.benchmarks          # 运行全部
    python -m ark.benchmarks --quick  # 快速模式
    python -m ark.benchmarks --json   # JSON输出
"""

import time
import json
from dataclasses import dataclass, field
from typing import Callable, List, Dict, Any
from statistics import mean, stdev

from pydantic import BaseModel

from .guard import IdempotencyGuard
from .breaker import CircuitBreaker
from .validator import OutputValidator


class _BenchSchema(BaseModel):
    """Minimal schema for benchmark validation."""
    status: str
    data: str = ""


@dataclass
class BenchmarkResult:
    name: str
    iterations: int
    total_ms: float
    avg_ms: float
    p50_ms: float
    p99_ms: float
    std_ms: float
    throughput_ops: float  # ops/sec

    def dict(self) -> Dict:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_ms": round(self.total_ms, 3),
            "avg_ms": round(self.avg_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "std_ms": round(self.std_ms, 3),
            "throughput_ops": round(self.throughput_ops, 1),
        }


class Benchmarks:
    """ARK 性能基准测试套件"""

    def __init__(self, iterations: int = 10_000):
        self.iterations = iterations
        self.results: List[BenchmarkResult] = []

    def _measure(self, name: str, fn: Callable, setup: Callable = None) -> BenchmarkResult:
        """运行N次测量"""
        timings = []
        for i in range(self.iterations):
            if setup and i == 0:
                setup()
            start = time.perf_counter()
            fn()
            elapsed = (time.perf_counter() - start) * 1000
            timings.append(elapsed)

        sorted_t = sorted(timings)
        n = len(sorted_t)
        return BenchmarkResult(
            name=name,
            iterations=n,
            total_ms=sum(timings),
            avg_ms=mean(timings),
            p50_ms=sorted_t[n // 2],
            p99_ms=sorted_t[int(n * 0.99)],
            std_ms=stdev(timings) if n > 1 else 0,
            throughput_ops=1000 / mean(timings),
        )

    def bench_idempotency_key_gen(self) -> BenchmarkResult:
        """幂等Key生成性能"""
        guard = IdempotencyGuard()
        args = {"tool": "send_email", "to": "test@ark.dev", "body": "hello" * 10}
        return self._measure(
            "IdempotencyGuard.key()",
            lambda: guard.key("send_email", args),
        )

    def bench_idempotency_check_hit(self) -> BenchmarkResult:
        """幂等Cache命中检查"""
        guard = IdempotencyGuard()
        key = guard.key("send_payment", {"amount": 100, "currency": "USD"})
        from .guard import ExecutionRecord
        guard.record(key, ExecutionRecord(
            idempotency_key=key,
            tool_name="send_payment",
            args_hash="abc12345",
            result={"status": "ok"},
        ))
        return self._measure(
            "IdempotencyGuard.check() [hit]",
            lambda: guard.check(key),
        )

    def bench_idempotency_check_miss(self) -> BenchmarkResult:
        """幂等Cache未命中检查"""
        guard = IdempotencyGuard()
        key = guard.key("new_tool", {"foo": "bar"})
        return self._measure(
            "IdempotencyGuard.check() [miss]",
            lambda: guard.check(key),
        )

    def bench_circuit_breaker_closed(self) -> BenchmarkResult:
        """熔断器→闭合状态（正常通路）"""
        cb = CircuitBreaker(name="bench")
        return self._measure(
            "CircuitBreaker.call() [closed]",
            lambda: cb.call(lambda: "ok"),
        )

    def bench_validator_valid(self) -> BenchmarkResult:
        """输出验证→有效输出"""
        v = OutputValidator()
        return self._measure(
            "OutputValidator.validate() [valid]",
            lambda: v.validate(_BenchSchema, {"status": "ok", "data": "test"}),
        )

    def bench_validator_none(self) -> BenchmarkResult:
        """输出验证→None输出（快速拦截）"""
        v = OutputValidator()
        return self._measure(
            "OutputValidator.validate() [none]",
            lambda: v.validate(_BenchSchema, None),
        )

    def bench_full_pipeline(self) -> BenchmarkResult:
        """全链路：Key→Guard→Breaker→Validator"""
        guard = IdempotencyGuard()
        cb = CircuitBreaker(name="pipeline")
        v = OutputValidator()
        return self._measure(
            "Full Pipeline (guard+breaker+validate)",
            lambda: self._run_pipeline(guard, cb, v),
        )

    def _run_pipeline(self, guard: IdempotencyGuard, cb: CircuitBreaker, v: OutputValidator):
        args = {"action": "call_api", "endpoint": "/v1/chat", "tokens": 1024}
        key = guard.key("agent_action", args)
        if guard.check(key):
            return
        result = cb.call(lambda: {"status": "ok", "data": "pipeline test"})
        from .guard import ExecutionRecord
        guard.record(key, ExecutionRecord(
            idempotency_key=key, tool_name="agent_action", args_hash="dummy", result=result
        ))
        v.validate(_BenchSchema, result)
        return result

    def run_all(self) -> List[BenchmarkResult]:
        """运行全部基准测试"""
        benchmarks = [
            ("Idempotency Key Gen", self.bench_idempotency_key_gen),
            ("Idempotency Check [hit]", self.bench_idempotency_check_hit),
            ("Idempotency Check [miss]", self.bench_idempotency_check_miss),
            ("CircuitBreaker [closed]", self.bench_circuit_breaker_closed),
            ("Validator [valid]", self.bench_validator_valid),
            ("Validator [none]", self.bench_validator_none),
            ("Full Pipeline", self.bench_full_pipeline),
        ]

        print(f"\n{'='*60}")
        print(f"  ARK v0.4.0 Benchmarks ({self.iterations:,} iterations each)")
        print(f"{'='*60}")
        print(f"{'Benchmark':<35} {'avg(μs)':>10} {'p50(μs)':>10} {'p99(μs)':>10} {'ops/s':>12}")
        print(f"{'-'*35} {'-'*10} {'-'*10} {'-'*10} {'-'*12}")

        for name, fn in benchmarks:
            result = fn()
            self.results.append(result)
            # Display in μs for sub-ms operations
            unit = "μs"
            scale = 1000
            print(
                f"{result.name:<35} "
                f"{result.avg_ms * scale:>10.1f} "
                f"{result.p50_ms * scale:>10.1f} "
                f"{result.p99_ms * scale:>10.1f} "
                f"{result.throughput_ops:>12,.0f}"
            )

        print(f"{'='*60}\n")
        return self.results

    def to_json(self) -> str:
        return json.dumps([r.dict() for r in self.results], indent=2)

    def summary(self) -> Dict[str, Any]:
        """生成汇总报告"""
        if not self.results:
            self.run_all()
        return {
            "version": "0.4.0-dev",
            "iterations": self.iterations,
            "results": [r.dict() for r in self.results],
            "slowest": max(self.results, key=lambda r: r.avg_ms).name,
            "fastest": min(self.results, key=lambda r: r.avg_ms).name,
            "total_time_ms": round(sum(r.total_ms for r in self.results), 3),
        }


# CLI entry point
if __name__ == "__main__":
    import sys
    quick = "--quick" in sys.argv
    output_json = "--json" in sys.argv

    b = Benchmarks(iterations=100 if quick else 10_000)
    b.run_all()

    if output_json:
        print(b.to_json())
    else:
        s = b.summary()
        print(f"🏆 Fastest: {s['fastest']}")
        print(f"🐢 Slowest: {s['slowest']}")
        print(f"⏱  Total: {s['total_time_ms']}ms")
