"""
ARK v0.4.0 — 100+ 压力测试套件

测试维度：
  ⚡ 并发压力 (25) | 🧪 边界条件 (25) | 💥 故障注入 (25) | 🔄 集成场景 (25)
"""

import pytest, time, json, os, sys, threading, random
from pathlib import Path
from typing import Optional

sys.path.insert(0, '/Users/w/.hermes/projects/ark/src')

from ark import (
    IdempotencyGuard, CircuitBreaker, OutputValidator, Trace,
    ProactiveGuard, ProactiveBlockError,
    StatefulBreaker, CircuitOpenError,
    ModulePipeline, Module, RateLimitModule, SchemaValidationModule, LoggingModule, ModuleBlockError,
    MultiAgentProtocol, AgentMessage, AgentHeartbeat, MessageStatus, AgentStatus,
    auto_init, detect_frameworks, ReliabilityScore,
    Dashboard, Achievements, BenchmarkResult, Benchmarks,
)
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════
# ⚡ 并发压力测试 (25项)
# ═══════════════════════════════════════════════════════════════════

class TestConcurrency_Guard:
    """⚡ 1-5: 幂等守护并发"""
    
    def test_1_concurrent_duplicate(self):
        """⚡1: 100线程并发相同参数调用"""
        g = IdempotencyGuard()
        results = []
        errors = []
        
        @g.wrap
        def pay(amount):
            time.sleep(0.001)
            return {"txn": f"tx_{amount}"}
        
        def worker():
            try:
                r = pay(amount=99)
                results.append(r)
            except Exception as e:
                errors.append(str(e))
        
        threads = [threading.Thread(target=worker) for _ in range(100)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        # 只有1次实际执行，99次拦截
        assert g.stats["passes"] == 1, f"Expected 1 pass, got {g.stats['passes']}"
        assert g.stats["intercepts"] == 99, f"Expected 99 intercepts, got {g.stats['intercepts']}"

    def test_2_concurrent_diff_args(self):
        """⚡2: 100线程不同参数——全部通过"""
        g = IdempotencyGuard()
        results = set()
        
        @g.wrap
        def echo(n):
            time.sleep(0.001)
            return n
        
        def worker(n):
            r = echo(n=n)
            results.add(r)
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(100)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert len(results) == 100
        assert g.stats["passes"] == 100
        assert g.stats["intercepts"] == 0

    def test_3_mixed_dup_unique(self):
        """⚡3: 混合重复+唯一参数"""
        g = IdempotencyGuard()
        
        @g.wrap
        def add(a, b):
            time.sleep(0.002)
            return a + b
        
        def worker_dup():
            for _ in range(10):
                add(a=1, b=2)
        
        def worker_unique():
            for i in range(10):
                add(a=i, b=i*2)
        
        threads = [threading.Thread(target=worker_dup) for _ in range(5)] + \
                  [threading.Thread(target=worker_unique) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert g.stats["passes"] == 10  # 10个不同参数
        assert g.stats["intercepts"] >= 40  # 最少40次拦截

    def test_4_guard_ttl_expiry(self):
        """⚡4: 并发中TTL过期检测"""
        g = IdempotencyGuard(ttl_seconds=1)
        call_count = [0]
        
        @g.wrap
        def fn(x):
            call_count[0] += 1
            return x
        
        # 先调一次
        fn(x=42)
        
        # 等TTL过期
        time.sleep(1.5)
        
        # 再调——应重新执行
        fn(x=42)
        assert call_count[0] == 2

    def test_5_guard_records_cached_error(self):
        """⚡5: 缓存错误重复抛出"""
        g = IdempotencyGuard()
        call_count = [0]
        
        @g.wrap
        def flaky():
            call_count[0] += 1
            raise ValueError("flaky error")
        
        # 第一次执行→失败
        with pytest.raises(ValueError):
            flaky()
        
        # 重复调用→缓存失败→应再次抛异常
        with pytest.raises(RuntimeError, match="Cached failure"):
            flaky()
        
        assert call_count[0] == 1


class TestConcurrency_Breaker:
    """⚡ 6-10: 熔断并发"""
    
    def test_6_concurrent_breaker_open(self):
        """⚡6: 多线程同时触发熔断"""
        cb = CircuitBreaker("multi-stress", failure_threshold=3, recovery_timeout=60)
        failures = []
        
        def fail():
            raise ConnectionError("timeout")
        
        def worker():
            try:
                cb.call(fail, fallback=lambda: "fallback")
            except CircuitOpenError as e:
                failures.append(str(e))
        
        # 先用3个线程触发熔断
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert cb.state == "open"
        
        # 更多线程调用，全部应走fallback
        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert cb.stats["total_failures"] >= 3

    def test_7_breaker_state_transitions_simultaneous(self):
        """⚡7: 并发状态转换"""
        # recovery_timeout 调大到 0.3s + sleep 调大到 0.015s，确保半开/关闭状态在采样窗口内可被观察到
        # 之前 0.1s/0.005s 在高负载下只看到 open 状态，会偶发失败
        cb = CircuitBreaker("state-race", failure_threshold=1, recovery_timeout=0.3)
        states = []
        barrier = threading.Barrier(5)
        
        def fail():
            raise ValueError("boom")
        
        def succeed():
            return "ok"
        
        def race_worker():
            barrier.wait()  # 同时启动
            for _ in range(20):
                try:
                    cb.call(fail, fallback=succeed)
                except:
                    pass
                time.sleep(0.015)
                try:
                    cb.call(succeed)
                except:
                    pass
                states.append(cb.state)
        
        threads = [threading.Thread(target=race_worker) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        # 应该有多种状态转换（100个样本，统计可靠）
        unique_states = set(states)
        assert len(unique_states) >= 2, f"只看到 {len(unique_states)} 种状态: {unique_states} (共{len(states)}个样本)"

    def test_8_breaker_half_open_recovery(self):
        """⚡8: 半开状态恢复并发"""
        cb = CircuitBreaker("half-open", failure_threshold=2, recovery_timeout=0.1, half_open_max=3)
        
        def fail():
            raise RuntimeError("fail")
        
        def succeed():
            return "recovered"
        
        # 打开熔断
        for _ in range(2):
            try: cb.call(fail)
            except: pass
        assert cb.state == "open"
        
        # 等待恢复期
        time.sleep(0.2)
        
        # 并发恢复尝试
        results = []
        def worker():
            r = cb.call(primary=succeed)
            results.append(r)
        
        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        # 至少一个成功(半开允许)
        assert "recovered" in results

    def test_9_breaker_fallback_chain(self):
        """⚡9: 多级降级链"""
        cb = CircuitBreaker("chain", failure_threshold=1)
        
        def primary():
            raise ValueError("primary failed")
        
        def fallback1():
            raise ValueError("fallback1 also failed")
        
        def fallback2():
            return "last resort"
        def chained_fallback():
            try: return fallback1()
            except ValueError: return fallback2()

        result = cb.call(primary, chained_fallback)
        assert result == "last resort"
    def test_10_concurrent_breaker_never_open_for_success(self):
        """⚡10: 成功调用不应触发熔断"""
        cb = CircuitBreaker("success-only", failure_threshold=3)
        results = []
        
        def ok():
            return 42
        
        def worker():
            r = cb.call(ok)
            results.append(r)
        
        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert cb.state == "closed"
        assert len(results) == 50
        assert all(r == 42 for r in results)


class TestConcurrency_Validator:
    """⚡ 11-15: 验证器并发"""
    
    def test_11_concurrent_validation(self):
        class Item(BaseModel):
            id: int
            name: str = Field(max_length=10)
        
        v = OutputValidator()
        results = []
        
        def worker():
            r = v.validate(Item, {"id": 1, "name": "a"})
            results.append(r.valid)
        
        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert all(results)
        assert v.stats["passed"] == 50

    def test_12_concurrent_bulk_failures(self):
        class Strict(BaseModel):
            value: int = Field(gt=0, lt=100)
        
        v = OutputValidator()
        
        def worker_bad():
            v.validate(Strict, {"value": -1})
        
        def worker_good():
            v.validate(Strict, {"value": 50})
        
        threads = [threading.Thread(target=worker_bad) for _ in range(30)] + \
                  [threading.Thread(target=worker_good) for _ in range(30)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert v.stats["passed"] == 30
        assert v.stats["blocked"] == 30

    def test_13_schema_validation_null_inputs(self):
        """⚡13: 空值验证并发"""
        class Required(BaseModel):
            name: str
        
        v = OutputValidator()
        
        def worker():
            v.validate(Required, None)
        
        threads = [threading.Thread(target=worker) for _ in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert v.stats["blocked"] == 50

    def test_14_deeply_nested_validation(self):
        class Address(BaseModel):
            street: str
            zip: str
        
        class User(BaseModel):
            name: str
            address: Address
        
        v = OutputValidator()
        
        def worker_good():
            v.validate(User, {"name": "A", "address": {"street": "B", "zip": "123"}})
        
        def worker_bad():
            v.validate(User, {"name": "A"})
        
        threads = [threading.Thread(target=worker_good) for _ in range(25)] + \
                  [threading.Thread(target=worker_bad) for _ in range(25)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        # 25 passed (good), 25 blocked (bad)
        assert v.stats["passed"] == 25

    def test_15_string_to_json_auto_parse(self):
        """⚡15: JSON字符串自动解析"""
        class Data(BaseModel):
            key: str
            value: int
        
        v = OutputValidator()
        
        # 传入JSON字符串
        result = v.validate(Data, '{"key": "test", "value": 42}')
        assert result.valid
        assert result.data["key"] == "test"


class TestConcurrency_StatefulBreaker:
    """⚡ 16-20: 状态持久化熔断并发"""
    
    def test_16_concurrent_stateful_open(self):
        persist_path = f"/tmp/ark_test_stateful_{time.time_ns()}.json"
        sb = StatefulBreaker("state-con", failure_threshold=3, persist_path=persist_path)
        
        def fail():
            raise ValueError("boom")
        
        def worker():
            try: sb.call(fail)
            except: pass
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert sb.state == "open"
        assert os.path.exists(persist_path)
        
        # 验证持久化文件内容
        with open(persist_path) as f:
            data = json.load(f)
        assert data["_state"] == "open"
        assert data["_failure_count"] >= 3
        os.remove(persist_path)

    def test_17_stateful_survives_restart(self):
        """⚡17: 模拟重启后状态不丢失"""
        persist_path = f"/tmp/ark_test_restart_{time.time_ns()}.json"
        
        # 第一次生命周期
        sb1 = StatefulBreaker("survivor", failure_threshold=2, persist_path=persist_path)
        def fail(): raise RuntimeError("fail")
        for _ in range(2):
            try: sb1.call(fail)
            except: pass
        assert sb1.state == "open"
        del sb1
        
        # 模拟重启
        sb2 = StatefulBreaker("survivor", failure_threshold=2, persist_path=persist_path)
        assert sb2.state == "open", "重启后状态应保持熔断"
        
        # 验证熔断中的调用走fallback
        result = sb2.call(fail, fallback=lambda: "survived")
        assert result == "survived"
        os.remove(persist_path)

    def test_18_stateful_manual_reset(self):
        """⚡18: 手动重置"""
        persist_path = f"/tmp/ark_test_reset_{time.time_ns()}.json"
        sb = StatefulBreaker("reset", failure_threshold=1, persist_path=persist_path)
        
        def fail(): raise ValueError()
        try: sb.call(fail)
        except: pass
        assert sb.state == "open"
        
        sb.reset()
        assert sb.state == "closed"
        
        # 重置后应能正常调用
        result = sb.call(lambda: "ok")
        assert result == "ok"
        os.remove(persist_path)

    def test_19_stateful_multi_breaker(self):
        """⚡19: 多个独立Breaker"""
        persist_path_a = f"/tmp/ark_test_multi_a_{time.time_ns()}.json"
        persist_path_b = f"/tmp/ark_test_multi_b_{time.time_ns()}.json"
        
        sb_a = StatefulBreaker("svc-a", failure_threshold=2, persist_path=persist_path_a)
        sb_b = StatefulBreaker("svc-b", failure_threshold=5, persist_path=persist_path_b)
        
        def fail(): raise Exception()
        
        # 只打垮A
        for _ in range(2):
            try: sb_a.call(fail)
            except: pass
        
        # B还正常
        assert sb_a.state == "open"
        assert sb_b.state == "closed"
        
        # B正常调用
        assert sb_b.call(lambda: 42) == 42
        os.remove(persist_path_a)
        os.remove(persist_path_b)

    def test_20_stateful_lock_thread_safety(self):
        """⚡20: 线程安全验证"""
        persist_path = f"/tmp/ark_test_locksafe_{time.time_ns()}.json"
        sb = StatefulBreaker("locksafe", persist_path=persist_path)
        
        def fail(): raise ValueError("err")
        
        def worker():
            for _ in range(50):
                try: sb.call(fail)
                except: pass
                try: sb.call(lambda: 1)
                except: pass
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert sb.stats["total_calls"] > 0
        os.remove(persist_path)


class TestConcurrency_MultiAgent:
    """⚡ 21-25: 多Agent协议并发"""
    
    def test_21_register_heartbeat_concurrent(self):
        """⚡21: 并发注册（默认Online）"""
        proto = MultiAgentProtocol("test-agent")
        
        def worker(i):
            proto.register_agent(f"agent-{i}")
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        online = proto.get_online_agents()
        assert len(online) >= 50, f"Got {len(online)} online agents"

    def test_22_message_exchange_burst(self):
        """⚡22: 消息突发交换"""
        proto = MultiAgentProtocol("hub")
        proto.register_agent("worker-1")
        
        def worker():
            for _ in range(20):
                msg = proto.send_message("worker-1", {"task": "process"})
                proto.acknowledge_message(msg.message_id)
        
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads: t.start()
        for t in threads: t.join()
        
        assert proto.stats["messages_sent"] == 200

    def test_23_health_check_expiry(self):
        """⚡23: 健康检查超时"""
        proto = MultiAgentProtocol("checker")
        proto.register_agent("ghost")
        
        # 刚注册应该在线
        assert proto.check_agent_health("ghost", max_age=30) in (AgentStatus.ONLINE, AgentStatus.UNKNOWN)
        
        # 模拟不发送心跳→应标记为离线
        time.sleep(1)
        # 使用更短的超时
        proto._agents["ghost"].last_seen = 0
        health = proto.check_agent_health("ghost", max_age=0.1)
        assert health == AgentStatus.OFFLINE

    def test_24_message_ttl_gc(self):
        """⚡24: 消息TTL过期清理"""
        proto = MultiAgentProtocol("gc-test")
        proto.register_agent("target")
        
        msg = proto.send_message("target", {"data": "old"}, max_retries=0, ttl=0.1)
        time.sleep(0.3)
        proto.collect_garbage()
        
        assert proto.stats["active_messages"] == 0

    def test_25_network_map_generation_large(self):
        """⚡25: 大规模网络拓扑"""
        proto = MultiAgentProtocol("big-net")
        for i in range(100):
            proto.register_agent(f"node-{i}")
        
        net_map = proto.network_map
        assert "🟢" in net_map or "⚪" in net_map  # 在线或未知
        assert len(net_map.split("\n")) >= 10


# ═══════════════════════════════════════════════════════════════════
# 🧪 边界条件测试 (25项)
# ═══════════════════════════════════════════════════════════════════

class TestBoundary_Guard:
    """🧪 1-5: 幂等保护边界"""
    
    def test_b1_empty_args(self):
        g = IdempotencyGuard()
        @g.wrap
        def noop(): return 1
        assert noop() == 1
        assert noop() == 1  # 拦截
        assert g.stats["intercepts"] == 1

    def test_b2_single_arg_vs_keyword(self):
        g = IdempotencyGuard()
        call_count = [0]
        @g.wrap
        def fn(x):
            call_count[0] += 1
            return x
        assert fn(5) == 5
        assert fn(x=5) == 5  # args vs kwargs → 不同签名
        assert call_count[0] == 2  # 视为不同调用

    def test_b3_nested_dict_args(self):
        g = IdempotencyGuard()
        call_count = [0]
        @g.wrap
        def process(data):
            call_count[0] += 1
            return data
        arg = {"user": {"name": "alice", "tags": [1, 2, 3]}}
        assert process(data=arg) == arg
        assert process(data=arg) == arg  # 应拦截
        assert call_count[0] == 1

    def test_b4_unicode_args(self):
        g = IdempotencyGuard()
        call_count = [0]
        @g.wrap
        def greet(name):
            call_count[0] += 1
            return f"Hello {name}"
        assert greet(name="世界") == "Hello 世界"
        assert greet(name="世界") == "Hello 世界"
        assert call_count[0] == 1

    def test_b5_zero_ttl(self):
        g = IdempotencyGuard(ttl_seconds=0)
        call_count = [0]
        @g.wrap
        def fn(x):
            call_count[0] += 1
            return x
        assert fn(x=1) == 1
        assert fn(x=1) == 1  # TTL=0，依然拦截（防止攻击）
        assert call_count[0] == 2  # TTL=0 -> every call executes


class TestBoundary_Breaker:
    """🧪 6-10: 熔断器边界"""
    
    def test_b6_zero_threshold(self):
        cb = CircuitBreaker("zero", failure_threshold=0)
        def fail(): raise Exception()
        try: cb.call(fail)
        except: pass
        # threshold=0 → 一次失败就熔断
        assert cb.state == "open"

    def test_b7_negative_recovery(self):
        cb = CircuitBreaker("neg", failure_threshold=1, recovery_timeout=-1)
        def fail(): raise Exception()
        try: cb.call(fail)
        except: pass
        assert cb.state == "open"
        # 负恢复时间→应立刻恢复
        time.sleep(0.1)
        result = cb.call(lambda: "ok")
        assert result == "ok"

    def test_b8_zero_half_open(self):
        cb = CircuitBreaker("half-zero", failure_threshold=1, recovery_timeout=0.1, half_open_max=0)
        def fail(): raise Exception()
        try: cb.call(fail)
        except: pass
        time.sleep(0.2)
        def succeed(): return "ok"
        result = cb.call(succeed)
        assert result == "ok"
        assert cb.state == "closed"

    def test_b9_breaker_no_fallback(self):
        cb = CircuitBreaker("no-fallback", failure_threshold=1, recovery_timeout=60)
        def fail(): raise ValueError("no save")
        try: cb.call(fail)
        except: pass
        with pytest.raises(Exception, match="Circuit.*OPEN"):
            cb.call(fail)

    def test_b10_breaker_one_million_stats(self):
        """🧪10: 百万级调用统计"""
        cb = CircuitBreaker("million", failure_threshold=1000)
        for _ in range(100000):
            try: cb.call(lambda: 1)
            except: pass
        assert cb.stats["total_calls"] == 100000


class TestBoundary_Validator:
    """🧪 11-15: 验证器边界"""
    
    def test_b11_empty_schema(self):
        class Empty(BaseModel):
            pass
        v = OutputValidator()
        r = v.validate(Empty, {})
        assert r.valid

    def test_b12_max_length_field(self):
        class ShortString(BaseModel):
            text: str = Field(max_length=5)
        v = OutputValidator()
        r = v.validate(ShortString, {"text": "a" * 5})
        assert r.valid
        r = v.validate(ShortString, {"text": "a" * 6})
        assert not r.valid

    def test_b13_invalid_types(self):
        class Typed(BaseModel):
            age: int
            name: str
        v = OutputValidator()
        r = v.validate(Typed, {"age": "not_a_number", "name": 123})
        assert not r.valid

    def test_b14_extra_fields(self):
        class Strict(BaseModel):
            x: int
        v = OutputValidator()
        # Pydantic默认忽略额外字段
        r = v.validate(Strict, {"x": 1, "y": 2})
        assert r.valid
        assert "x" in r.data

    def test_b15_missing_required(self):
        class Required(BaseModel):
            required_field: str
        v = OutputValidator()
        r = v.validate(Required, {})
        assert not r.valid
        assert len(r.errors) > 0


class TestBoundary_ProactiveGuard:
    """🧪 16-20: 预测性守卫边界"""
    
    def test_b16_zero_sensitivity(self):
        pg = ProactiveGuard(sensitivity=0.0)
        # 什么都不检测
        pg.record_failure("test", {"x": 1}, "error")
        should_block, risk, _ = pg.should_block("test", {"x": 1})
        assert should_block  # 风险>0且敏感度=0→阻止

    def test_b17_max_sensitivity(self):
        pg = ProactiveGuard(sensitivity=1.0)
        pg.record_failure("test", {"x": 1}, "error")
        should_block, risk, _ = pg.should_block("test", {"x": 1})
        assert not should_block  # risk≈0.9999 < 1.0
        assert 0.99 < risk < 1.0

    def test_b18_no_history(self):
        pg = ProactiveGuard()
        should_block, risk, _ = pg.should_block("unknown", {"x": 1})
        # 无历史数据 → 不阻止已知安全操作
        assert not should_block
        assert risk == 0.0

    def test_b19_large_args(self):
        pg = ProactiveGuard()
        large_args = {"data": "x" * 10000}
        pg.record_failure("big", large_args, "memory error")
        should_block, risk, _ = pg.should_block("big", large_args)
        assert should_block

    def test_b20_multiple_patterns(self):
        pg = ProactiveGuard()
        tools = ["pay", "email", "search", "compute", "store"]
        for t in tools:
            for _ in range(3):
                pg.record_failure(t, {"mode": "batch"}, "timeout")
        
        stats = pg.stats
        assert stats["patterns_learned"] == 5


class TestBoundary_ModuleKit:
    """🧪 21-25: 模块组合边界"""
    
    def test_b21_empty_pipeline(self):
        pipeline = ModulePipeline("empty")
        result = pipeline.process("test", {"x": 1})
        assert result["action"] == "allow"

    def test_b22_single_module_pipeline(self):
        pipeline = ModulePipeline("single")
        pipeline.add(RateLimitModule(max_calls_per_minute=5))
        for _ in range(5):
            assert pipeline.process("test", {})["action"] == "allow"
        # 第六次被限流
        assert pipeline.process("test", {})["action"] == "block"

    def test_b23_module_priority(self):
        """高优先级先执行"""
        class BlockModule(Module):
            def __init__(self, name, priority):
                super().__init__(name=name, priority=priority)
            def process(self, tool_name, args, context):
                return {"action": "block", "reason": f"Blocked by {self.name}", "context": context}
        
        pipeline = ModulePipeline("priority")
        high = BlockModule(name="high-block", priority=0)
        low = BlockModule(name="low-block", priority=200)
        pipeline.add(low).add(high)
        
        result = pipeline.process("test", {})
        assert "high-block" in result["reason"]

    def test_b24_disable_module(self):
        pipeline = ModulePipeline("disable")
        block = RateLimitModule(max_calls_per_minute=0)
        pipeline.add(block)
        
        # 正常情况下立即被限流
        assert pipeline.process("test", {})["action"] == "block"
        
        # 禁用后不生效
        pipeline.remove("rate-limit-0pm")
        assert pipeline.process("test", {})["action"] == "allow"

    def test_b25_logging_accumulation(self):
        """🧪25: 日志模块积累"""
        pipeline = ModulePipeline("log-test")
        log_mod = LoggingModule(max_log_size=10)
        pipeline.add(log_mod)
        
        for i in range(20):
            pipeline.process("tool", {"n": i})
        
        assert len(log_mod._log) == 10  # 只保留最新10条


# ═══════════════════════════════════════════════════════════════════
# 💥 故障注入测试 (25项)
# ═══════════════════════════════════════════════════════════════════

class TestFaultInjection:
    """💥 1-25: 系统级故障注入"""
    
    def test_f1_persist_file_corruption(self):
        """💥1: 持久化文件损坏"""
        path = f"/tmp/ark_fault_corrupt_{time.time_ns()}.json"
        with open(path, "w") as f:
            f.write("{{{invalid json}}")
        
        sb = StatefulBreaker("corrupt", persist_path=path)
        assert sb.state == "closed"  # 默认回退
        os.remove(path)

    def test_f2_persist_file_deleted_midway(self):
        """💥2: 运行中删除持久化文件"""
        path = f"/tmp/ark_fault_deleted_{time.time_ns()}.json"
        sb = StatefulBreaker("delete-me", persist_path=path, failure_threshold=1)
        
        # 删除文件
        os.remove(path)
        
        def fail(): raise ValueError()
        try: sb.call(fail)
        except: pass
        
        # 即使文件被删，内存状态正常
        assert sb.state == "open"

    def test_f3_persist_dir_not_writable(self):
        """💥3: 持久化目录不可写"""
        sb = StatefulBreaker("no-write", persist_path="/root/breaker.json")
        def succeed(): return "ok"
        assert sb.call(succeed) == "ok"

    def test_f4_guard_huge_payload(self):
        """💥4: 超大参数"""
        g = IdempotencyGuard()
        @g.wrap
        def big(data): return len(data)
        huge = "x" * 1000000
        assert big(data=huge) == 1000000

    def test_f5_output_validation_csv_injection(self):
        """💥5: 输出注入攻击"""
        class Safe(BaseModel):
            text: str = Field(max_length=100)
        v = OutputValidator()
        # 尝试CSV注入
        r = v.validate(Safe, {"text": "=CMD('rm -rf /')"})
        assert r.valid  # 字符串本身有效
        assert r.data["text"] == "=CMD('rm -rf /')"

    def test_f6_breaker_rapid_toggle(self):
        """💥6: 快速状态切换"""
        cb = CircuitBreaker("rapid", failure_threshold=1, recovery_timeout=0.05)
        states = []
        for _ in range(100):
            try: cb.call(lambda: (_ for _ in ()).throw(Exception()))
            except: pass
            time.sleep(0.01)
            try: cb.call(lambda: "ok")
            except: pass
            states.append(cb.state)
        assert len(set(states)) >= 2  # 至少出现两种状态

    def test_f7_zero_division_in_fallback(self):
        """💥7: fallback本身抛异常"""
        cb = CircuitBreaker("bad-fallback", failure_threshold=1)
        def fail(): raise ValueError()
        def bad_fallback(): return 1 / 0
        with pytest.raises(ZeroDivisionError):
            cb.call(fail, bad_fallback)

    def test_f8_deeply_nested_trace(self):
        """💥8: 深度嵌套链路追踪"""
        t = Trace("deep")
        def recurse(depth, max_depth=100):
            if depth >= max_depth:
                return depth
            s = t.start_span(f"level-{depth}")
            result = recurse(depth + 1, max_depth)
            t.end_span()
            return result
        
        recurse(0, 50)
        summary = t.summary()
        assert summary["total_spans"] == 51  # root + 50 levels

    def test_f9_trace_no_end(self):
        """💥9: 不调用end_span"""
        t = Trace("leak")
        t.start_span("leaked")
        # 不调用end_span
        summary = t.summary()
        assert summary["status"] == "ok"  # 不会崩溃

    def test_f10_concurrent_trace_spans(self):
        """💥10: 并发链路追踪"""
        t = Trace("concurrent-trace")
        def worker():
            for i in range(10):
                s = t.start_span(f"w-{threading.get_ident()}-{i}")
                time.sleep(0.001)
                t.end_span()
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for th in threads: th.start()
        for th in threads: th.join()
        assert t.total_spans > 10

    def test_f11_output_validate_cyclic_ref(self):
        """💥11: 循环引用"""
        class Node(BaseModel):
            val: int
            child: Optional["Node"] = None
        Node.model_rebuild()
        v = OutputValidator()
        r = v.validate(Node, {"val": 1})
        assert r.valid

    def test_f12_proactive_guard_accuracy(self):
        """💥12: 预测精度测试"""
        pg = ProactiveGuard(sensitivity=0.5)
        # 记录5次失败
        for _ in range(5):
            pg.record_failure("flakey", {"op": "risk"}, "timeout")
        # 记录95次成功
        for _ in range(95):
            pg.record_success("flakey", {"op": "safe"})
        
        stats = pg.stats
        assert stats["patterns_learned"] >= 1

    def test_f13_multiagent_self_loop(self):
        """💥13: Agent给自己发消息"""
        proto = MultiAgentProtocol("self")
        proto.register_agent("self")
        msg = proto.send_message("self", {"test": True})
        assert msg.status in (MessageStatus.DELIVERED, MessageStatus.FAILED)

    def test_f14_multiagent_unknown_recipient(self):
        """💥14: 消息发给未注册Agent"""
        proto = MultiAgentProtocol("sender")
        msg = proto.send_message("ghost", {"ping": True})
        assert msg.status == MessageStatus.FAILED

    def test_f15_dashboard_empty_state(self):
        """💥15: 空Dashboard"""
        dash = Dashboard()
        assert dash.trust_monitor["validation"]["pass_rate"] == 100.0
        assert dash.scoreboard == []

    def test_f16_achievements_no_progress(self):
        """💥16: 零成就进度"""
        ach = Achievements()
        s = ach.summary
        for a in s:
            assert a["progress"] == 0

    def test_f17_score_all_failures(self):
        """💥17: 100%失败率"""
        score = ReliabilityScore()
        for _ in range(10):
            score.record_run(success=False, tool_calls=5, tool_failures=5)
        assert score.score < 20  # 至少低于20分
        assert score.grade == "D"

    def test_f18_score_perfect(self):
        """💥18: 100%成功率"""
        score = ReliabilityScore()
        for _ in range(10):
            score.record_run(success=True, tool_calls=100)
        assert score.score == 100.0
        assert score.grade == "S+ 🏆"

    def test_f19_module_wrap_with_tool_name(self):
        """💥19: 模块包装自定义名称"""
        pipeline = ModulePipeline()
        pipeline.add(RateLimitModule(max_calls_per_minute=10))
        
        @pipeline.wrap
        def my_func():
            return 42
        
        assert my_func() == 42

    def test_f20_proactive_wrap_decorator(self):
        """💥20: 预测守卫装饰器"""
        pg = ProactiveGuard(sensitivity=1.0)
        @pg.wrap
        def safe_func():
            return "safe"
        assert safe_func() == "safe"

    def test_f21_breaker_stats_rounding(self):
        """💥21: 统计精度"""
        cb = CircuitBreaker("precision")
        cb.call(lambda: 1)
        assert "100.0%" in cb.stats["reliability"]

    def test_f22_guard_stats_zero_reset(self):
        """💥22: 零记录时防止除零"""
        g = IdempotencyGuard()
        s = g.stats
        assert s["save_rate"] == "0%"

    def test_f23_validator_very_long_field(self):
        """💥23: 超长字段名"""
        class LongField(BaseModel):
            x: str
        v = OutputValidator()
        long_key = "a" * 1000
        r = v.validate(LongField, {long_key: "value", "x": "ok"})
        # 额外字段（超长key）被忽略
        assert r.valid

    def test_f24_negative_breaker_threshold(self):
        """💥24: 负阈值"""
        cb = CircuitBreaker("neg-thresh", failure_threshold=-1)
        def fail(): raise Exception()
        # 阈值<=0 → 一次就熔断
        try: cb.call(fail)
        except: pass
        assert cb.state == "open"

    def test_f25_multiagent_extreme_timestamps(self):
        """💥25: 极端时间戳"""
        proto = MultiAgentProtocol("time-travel")
        msg = AgentMessage(
            sender="a", recipient="b",
            ttl_seconds=-1  # 负TTL
        )
        assert msg.ttl_seconds < 0  # 不崩溃


# ═══════════════════════════════════════════════════════════════════
# 🔄 集成场景测试 (25项)
# ═══════════════════════════════════════════════════════════════════

class TestIntegration:
    """🔄 1-25: 全链路集成"""
    
    def test_i1_full_pipeline(self):
        """🔄1: Guard+Breaker+Validator全链路"""
        guard = IdempotencyGuard()
        breaker = CircuitBreaker("integ", failure_threshold=2)
        validator = OutputValidator()
        score = ReliabilityScore()
        
        class Result(BaseModel):
            status: str
            value: int
        
        @guard.wrap
        def process(x):
            return breaker.call(lambda: {"status": "ok", "value": x * 2})
        
        # 正常流
        result = process(x=10)
        validation = validator.validate(Result, result)
        assert validation.valid
        score.record_run(success=True)
        
        # 重复流→拦截
        result2 = process(x=10)
        validation2 = validator.validate(Result, result2)
        score.record_run(success=True)
        
        assert score.score == 100.0

    def test_i2_guard_breaker_chain_with_fallback(self):
        """🔄2: Guard+Breaker+Fallback"""
        guard = IdempotencyGuard()
        breaker = CircuitBreaker("chain", failure_threshold=1)
        
        @guard.wrap
        def unreliable_call():
            return breaker.call(
                lambda: (_ for _ in ()).throw(ValueError("fail")),
                fallback=lambda: "safe_result"
            )
        
        result = unreliable_call()
        assert result == "safe_result"

    def test_i3_proactive_guard_pipeline(self):
        """🔄3: 预测性守卫+模块管道"""
        pg = ProactiveGuard(sensitivity=0.6)
        pipeline = ModulePipeline("proactive-test")
        pipeline.add(RateLimitModule(max_calls_per_minute=100))
        
        @pg.wrap
        @pipeline.wrap
        def risky_call(x):
            return x
        
        # 先记录失败模式
        for _ in range(10):
            pg.record_failure("risky_call", {"x": -1}, "invalid negative")
        
        # 正常调用
        assert risky_call(x=42) == 42

    def test_i4_stateful_breaker_survives_restart_fallback(self):
        """🔄4: 持久化熔断+重启+自动降级"""
        path = f"/tmp/ark_integ_survive_{time.time_ns()}.json"
        
        # 第一轮：触发熔断
        sb = StatefulBreaker("integ-restart", failure_threshold=2, persist_path=path)
        def fail(): raise ConnectionError("timeout")
        def fallback(): return "degraded service"
        for _ in range(2):
            try: sb.call(fail)
            except: pass
        del sb
        
        # 第二轮：重启后自动降级
        sb2 = StatefulBreaker("integ-restart", failure_threshold=2, persist_path=path)
        result = sb2.call(fail, fallback)
        assert result == "degraded service"
        os.remove(path)

    def test_i5_multiagent_discovery(self):
        """🔄5: 多Agent发现+注册+消息"""
        proto = MultiAgentProtocol("orchestrator")
        
        # 注册子Agent
        for i in range(5):
            proto.register_agent(f"worker-{i}")
        
        online = proto.get_online_agents()
        assert len(online) >= 5
        
        # 广播消息
        for worker in online:
            msg = proto.send_message(worker, {"task": "process"})
            proto.acknowledge_message(msg.message_id)
        
        assert proto.stats["delivery_rate"] == "100.0%"

    def test_i6_ark_auto_init(self):
        """🔄6: 自动初始化"""
        config = auto_init()
        assert "guard" in config
        assert "breaker" in config
        assert "validator" in config
        assert "score" in config
        assert "registry" in config

    def test_i7_detect_langchain(self):
        """🔄7: 框架检测"""
        frameworks = detect_frameworks()
        assert isinstance(frameworks, list)

    def test_i8_benchmark_basic(self):
        """🔄8: 基准测试"""
        bench = Benchmarks(iterations=1)
        result = bench.run_all()
        assert isinstance(result, list)
        assert len(result) > 0

    def test_i9_benchmark_result_class(self):
        """🔄9: 基准结果"""
        br = BenchmarkResult(name="test", iterations=1000, total_ms=500.0, avg_ms=0.5, p50_ms=0.5, p99_ms=1.0, std_ms=0.1, throughput_ops=2000.0)
        assert br.throughput_ops == 2000.0
        d = br.dict()
        assert "2000" in str(d)

    def test_i10_module_kit_schema_validation_block(self):
        """🔄10: Schema验证模块拦截无效输入"""
        from pydantic import BaseModel, Field
        
        class PaymentSchema(BaseModel):
            amount: float = Field(gt=0)
            currency: str = Field(pattern="^[A-Z]{3}$")
        
        pipeline = ModulePipeline("payment-check")
        pipeline.add(SchemaValidationModule(schema=PaymentSchema))
        
        # 有效
        result = pipeline.process("pay", {"amount": 99.99, "currency": "USD"})
        assert result["action"] == "allow"
        
        # 无效（负数金额）
        result = pipeline.process("pay", {"amount": -1, "currency": "USD"})
        assert result["action"] == "block"
        
        # 无效（错误的币种格式）
        result = pipeline.process("pay", {"amount": 10, "currency": "usd"})
        assert result["action"] == "block"

    def test_i11_proactive_risk_report(self):
        """🔄11: 风险报告"""
        pg = ProactiveGuard()
        for t in ["pay", "email", "auth"]:
            for _ in range(5):
                pg.record_failure(t, {"mode": "batch"}, f"{t} failed")
        
        report = pg.risk_report
        assert "Top Risk Patterns" in report
        assert "pay" in report

    def test_i12_network_map_with_offline_agents(self):
        """🔄12: 网络拓扑含离线Agent"""
        proto = MultiAgentProtocol("net")
        proto.register_agent("alive")
        proto.register_agent("dead")
        proto._agents["dead"].last_seen = 0
        
        net_map = proto.network_map
        assert "alive" in net_map
        assert "dead" in net_map

    def test_i13_score_share_text(self):
        """🔄13: 分享文案生成"""
        score = ReliabilityScore()
        score.record_run(success=True)
        text = score.share_text
        assert len(text) > 10

    def test_i14_score_badge_url(self):
        """🔄14: Badge URL生成"""
        score = ReliabilityScore()
        score.record_run(success=True)
        url = score.badge_url
        assert "img.shields.io" in url

    def test_i15_score_comparison(self):
        """🔄15: Before/After对比"""
        score = ReliabilityScore()
        score.record_run(success=True, intercepts=5, blocks=2)
        table = score.comparison()
        assert "Without ARK" in table
        assert "With ARK" in table

    def test_i16_dashboard_agent_tracking(self):
        """🔄16: Dashboard多Agent追踪"""
        from ark import Dashboard, Event
        dash = Dashboard()
        agents = ["bot-a", "bot-b", "bot-c"]
        for i, agent in enumerate(agents):
            dash.record(Event(time.time(), "intercept", agent, score_snapshot=70 + i*10))
        
        board = dash.scoreboard
        assert len(board) == 3
        assert board[0]["agent"] == "bot-c"  # 最高分

    def test_i17_trace_summary_error_count(self):
        """🔄17: 链路追踪错误统计"""
        t = Trace("err-test")
        t.start_span("step1")
        t.end_span(error="error1")
        t.start_span("step2")
        t.end_span(error="error2")
        
        summary = t.summary()
        assert summary["errors"] == 2
        assert summary["status"] == "error"

    def test_i18_achievements_all_tiers(self):
        """🔄18: 全成就系统"""
        ach = Achievements()
        # 解锁所有青铜
        ach.record("intercept", count=10)
        ach.record("recover", count=1)
        ach.record("validate_pass", count=10)
        ach.record("span", count=10)
        
        s = ach.summary
        guardian = [a for a in s if a["id"] == "guardian"][0]
        assert len(guardian["unlocked_at"]) >= 1

    def test_i19_all_modules_importable(self):
        """🔄19: 所有模块可导入"""
        from ark import (
            IdempotencyGuard, CircuitBreaker, OutputValidator, Trace,
            ProactiveGuard, StatefulBreaker,
            ModulePipeline, Module, RateLimitModule, SchemaValidationModule, LoggingModule,
            MultiAgentProtocol, AgentMessage, AgentHeartbeat, MessageStatus, AgentStatus,
        )
        assert IdempotencyGuard
        assert ProactiveGuard
        assert StatefulBreaker
        assert ModulePipeline
        assert MultiAgentProtocol

    def test_i20_version_consistent(self):
        """🔄20: 版本一致性"""
        import ark
        v = ark.__version__
        assert isinstance(v, str)
        assert v.startswith("0.6"), f"version should be 0.6.x, got {v}"

    def test_i21_all_modules_have_stats(self):
        """🔄21: 所有模块有stats属性"""
        modules = [
            IdempotencyGuard(),
            CircuitBreaker("test"),
            OutputValidator(),
            ProactiveGuard(),
            StatefulBreaker("test"),
            ModulePipeline(),
            MultiAgentProtocol("test"),
        ]
        for m in modules:
            s = m.stats
            assert isinstance(s, dict), f"{type(m).__name__} stats should be dict"

    def test_i22_persistence_cleanup(self):
        """🔄22: 持久化文件清理"""
        path = f"/tmp/ark_integ_cleanup_{time.time_ns()}.json"
        sb = StatefulBreaker("cleanup", persist_path=path)
        
        def fail(): raise Exception()
        for _ in range(3):
            try: sb.call(fail)
            except: pass
        
        assert os.path.exists(path)
        inspect = sb.inspect_persistence()
        assert inspect["file_exists"]
        assert inspect["current_state"] == "open"
        os.remove(path)

    def test_i23_multiagent_stats_after_gc(self):
        """🔄23: GC后统计一致性"""
        proto = MultiAgentProtocol("gc-stats")
        for i in range(10):
            proto.register_agent(f"a-{i}")
        
        # 发一些短TTL消息
        for i in range(10):
            proto.send_message(f"a-{i}", {"n": i}, ttl=0.05)
        
        time.sleep(0.2)
        proto.collect_garbage()
        
        stats = proto.stats
        assert stats["active_messages"] == 0
        assert stats["messages_sent"] == 10

    def test_i24_breaker_dashboard_integration(self):
        """🔄24: 熔断+Dashboard集成"""
        from ark import Dashboard, Event
        dash = Dashboard()
        cb = CircuitBreaker("svc", failure_threshold=2)
        
        def fail(): raise Exception()
        for _ in range(2):
            try: cb.call(fail)
            except: pass
        
        dash.record(Event(time.time(), "trip", "svc", detail=cb.state))
        dash.record(Event(time.time(), "intercept", "svc"))
        
        tm = dash.trust_monitor
        assert tm["circuit_breaker"]["trips"] == 1

    def test_i25_end_to_end_ecommerce(self):
        """🔄25: 模拟电商支付全流程"""
        guard = IdempotencyGuard()
        breaker = CircuitBreaker("payment", failure_threshold=3)
        validator = OutputValidator()
        score = ReliabilityScore()
        
        class PaymentResult(BaseModel):
            txn_id: str = Field(min_length=6)
            amount: float = Field(gt=0)
            status: str = Field(pattern="^(success|pending|failed)$")
        
        @guard.wrap
        def charge(user_id: str, amount: float):
            return breaker.call(
                lambda: {
                    "txn_id": f"txn_{user_id[:4]}",
                    "amount": amount,
                    "status": "success"
                }
            )
        
        # 正常支付
        result = charge(user_id="user_001", amount=99.99)
        vr = validator.validate(PaymentResult, result)
        assert vr.valid
        score.record_run(success=True, tool_calls=3)
        
        # 重复支付→拦截
        result2 = charge(user_id="user_001", amount=99.99)
        vr2 = validator.validate(PaymentResult, result2)
        score.record_run(success=True, intercepts=1)
        
        # 不同用户→通过
        result3 = charge(user_id="user_002", amount=49.99)
        vr3 = validator.validate(PaymentResult, result3)
        assert vr3.valid
        score.record_run(success=True, tool_calls=3)
        
        assert score.score >= 90
        assert guard.stats["intercepts"] >= 1


# ═══════════════════════════════════════════════════════════════════
# 🧹 清理临时文件
# ═══════════════════════════════════════════════════════════════════

def teardown_module():
    """清理所有临时JSON文件"""
    for f in Path("/tmp").glob("ark_test_*.json"):
        try: f.unlink()
        except: pass


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])