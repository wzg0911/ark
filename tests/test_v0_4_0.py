"""Tests for ARK v0.4.0 Benchmarks module."""

import pytest
from ark.benchmarks import Benchmarks, BenchmarkResult


class TestBenchmarks:
    def test_bench_idempotency_key_gen(self):
        b = Benchmarks(iterations=50)
        r = b.bench_idempotency_key_gen()
        assert isinstance(r, BenchmarkResult)
        assert r.iterations == 50
        assert r.avg_ms > 0
        assert r.throughput_ops > 0

    def test_bench_idempotency_check_hit(self):
        b = Benchmarks(iterations=50)
        r = b.bench_idempotency_check_hit()
        assert r.iterations == 50
        assert r.avg_ms > 0

    def test_bench_idempotency_check_miss(self):
        b = Benchmarks(iterations=50)
        r = b.bench_idempotency_check_miss()
        assert r.iterations == 50
        assert r.avg_ms < 0.01  # should be very fast (microseconds)

    def test_bench_circuit_breaker_closed(self):
        b = Benchmarks(iterations=50)
        r = b.bench_circuit_breaker_closed()
        assert r.iterations == 50
        assert r.throughput_ops > 30_000  # fast path (MacBook Air ~37k w/ harness overhead)

    def test_bench_validator_valid(self):
        b = Benchmarks(iterations=50)
        r = b.bench_validator_valid()
        assert r.iterations == 50
        assert r.avg_ms > 0

    def test_bench_validator_none(self):
        b = Benchmarks(iterations=50)
        r = b.bench_validator_none()
        assert r.iterations == 50
        assert r.avg_ms > 0

    def test_bench_full_pipeline(self):
        b = Benchmarks(iterations=50)
        r = b.bench_full_pipeline()
        assert r.iterations == 50
        assert r.avg_ms > 0

    def test_run_all_returns_results(self):
        b = Benchmarks(iterations=50)
        results = b.run_all()
        assert len(results) >= 7
        for r in results:
            assert isinstance(r, BenchmarkResult)
            assert r.iterations == 50

    def test_summary(self):
        b = Benchmarks(iterations=50)
        summary = b.summary()
        assert "version" in summary
        assert "results" in summary
        assert "fastest" in summary
        assert "slowest" in summary
        assert "total_time_ms" in summary
        assert len(summary["results"]) >= 7

    def test_to_json(self):
        b = Benchmarks(iterations=50)
        b.run_all()
        data = b.to_json()
        import json
        parsed = json.loads(data)
        assert isinstance(parsed, list)
        assert len(parsed) >= 7

    def test_benchmark_result_dict(self):
        r = BenchmarkResult(
            name="test", iterations=100, total_ms=10.0,
            avg_ms=0.1, p50_ms=0.09, p99_ms=0.15,
            std_ms=0.02, throughput_ops=10000.0,
        )
        d = r.dict()
        assert d["name"] == "test"
        assert d["iterations"] == 100
        assert d["avg_ms"] == 0.1
        assert d["throughput_ops"] == 10000.0
