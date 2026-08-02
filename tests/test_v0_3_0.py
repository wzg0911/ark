"""
ARK v0.3.0 tests — Dashboard + Achievements + Integration
"""
import pytest, time, sys
sys.path.insert(0, '/Users/w/.hermes/projects/ark/src')

from ark import (
    Dashboard, Event, get_dashboard,
    Achievements, Achievement,
    IdempotencyGuard, CircuitBreaker, OutputValidator, Trace,
)


# ═══════════════════════════════════════════════════════════════
# Dashboard tests
# ═══════════════════════════════════════════════════════════════

class TestDashboard:
    def test_record_intercept(self):
        dash = Dashboard()
        dash.record(Event(ts=time.time(), kind="intercept", agent="bot-a"))
        assert dash._global_intercepts == 1
        assert dash.agents["bot-a"]["intercepts"] == 1

    def test_record_multiple_kinds(self):
        dash = Dashboard()
        for kind in ["intercept", "block", "trip", "recover", "validate_pass", "validate_fail", "span"]:
            dash.record(Event(ts=time.time(), kind=kind, agent="bot"))
        assert dash._global_intercepts == 1
        assert dash._global_blocks == 1
        assert dash._global_trips == 1
        assert dash._global_recoveries == 1
        assert dash._global_validate_passes == 1
        assert dash._global_validate_fails == 1
        assert dash._global_spans == 1

    def test_trust_monitor(self):
        dash = Dashboard()
        dash.record(Event(ts=time.time(), kind="validate_pass", agent="bot"))
        dash.record(Event(ts=time.time(), kind="validate_pass", agent="bot"))
        dash.record(Event(ts=time.time(), kind="validate_fail", agent="bot"))
        tm = dash.trust_monitor
        assert tm["validation"]["passes"] == 2
        assert tm["validation"]["fails"] == 1
        assert tm["validation"]["pass_rate"] == pytest.approx(66.7, 0.1)

    def test_trust_monitor_empty(self):
        dash = Dashboard()
        tm = dash.trust_monitor
        assert tm["validation"]["pass_rate"] == 100.0
        assert tm["idempotency"]["status"] == "⚪"

    def test_scoreboard_sorting(self):
        dash = Dashboard()
        # bot-a: score 90
        dash.record(Event(ts=time.time(), kind="intercept", agent="bot-a", score_snapshot=90.0))
        dash.record(Event(ts=time.time(), kind="intercept", agent="bot-a", score_snapshot=90.0))
        # bot-b: score 95
        dash.record(Event(ts=time.time(), kind="intercept", agent="bot-b", score_snapshot=95.0))
        # bot-c: score 50
        dash.record(Event(ts=time.time(), kind="intercept", agent="bot-c", score_snapshot=50.0))

        board = dash.scoreboard
        assert board[0]["agent"] == "bot-b"
        assert board[0]["avg_reliability"] == 95.0
        assert board[-1]["agent"] == "bot-c"

    def test_scoreboard_empty(self):
        dash = Dashboard()
        assert dash.scoreboard == []

    def test_trace_explorer(self):
        dash = Dashboard()
        dash.record(Event(ts=time.time(), kind="span", agent="bot", detail="checkout"))
        dash.record(Event(ts=time.time(), kind="span", agent="bot", detail="payment"))
        te = dash.trace_explorer
        assert te["total_spans"] == 2
        assert len(te["latest_10"]) == 2

    def test_render_text(self):
        dash = Dashboard()
        dash.record(Event(ts=time.time(), kind="intercept", agent="bot-x"))
        text = dash.render()
        assert "Trust Monitor" in text
        assert "Scoreboard" in text
        assert "Trace Explorer" in text
        assert "bot-x" in text

    def test_to_json(self):
        dash = Dashboard()
        dash.record(Event(ts=time.time(), kind="block", agent="bot"))
        j = dash.to_json()
        assert '"trust_monitor"' in j
        assert '"scoreboard"' in j

    def test_get_dashboard_singleton(self):
        d1 = get_dashboard()
        d2 = get_dashboard()
        assert d1 is d2


# ═══════════════════════════════════════════════════════════════
# Achievements tests
# ═══════════════════════════════════════════════════════════════

class TestAchievements:
    def test_guardian_bronze_unlock(self):
        ach = Achievements()
        # target is 10 for bronze Guardian
        for _ in range(9):
            ach.record("intercept", agent="bot")
        unlocks = ach.record("intercept", agent="bot")  # 10th
        assert len(unlocks) >= 1
        assert any("Guardian" in u for u in unlocks)

    def test_guardian_silver_unlock(self):
        ach = Achievements()
        for _ in range(100):
            ach.record("intercept", agent="bot")
        # Should have unlocked Bronze (10) and Silver (100)
        g = ach.achievements["guardian"]
        assert len(g.unlocked_at) >= 2

    def test_survivor_bronze_unlock(self):
        ach = Achievements()
        unlocks = ach.record("recover", agent="bot")  # target=1
        assert len(unlocks) >= 1
        assert any("Survivor" in u for u in unlocks)

    def test_inspector_progress(self):
        ach = Achievements()
        ach.record("validate_pass", agent="bot", count=5)
        insp = ach.achievements["inspector"]
        assert insp.progress == 5
        assert not insp.unlocked_at  # need 10

    def test_summary_has_all_achievements(self):
        ach = Achievements()
        s = ach.summary
        ids = {a["id"] for a in s}
        assert "guardian" in ids
        assert "survivor" in ids
        assert "inspector" in ids
        assert "watcher" in ids
        assert "ark_master" in ids

    def test_render_achievements(self):
        ach = Achievements()
        ach.record("intercept", count=10)
        text = ach.render()
        assert "Achievements" in text
        assert "Guardian" in text

    def test_ark_master_unlock(self):
        ach = Achievements()
        # Unlock all 4 core at Bronze
        ach.record("intercept", count=10)
        ach.record("recover", count=1)
        ach.record("validate_pass", count=10)
        # Bronze doesn't trigger master (needs Gold = 3 tiers)
        master = ach.achievements["ark_master"]
        assert not master.is_maxed  # Not unlocked at bronze

        # Push to Gold for all
        ach.record("intercept", count=90)   # total 100 → Silver
        ach.record("recover", count=9)      # total 10  → Silver
        ach.record("validate_pass", count=90)  # total 100 → Silver
        ach.record("span", count=10)        # Bronze

        # Need Gold for all: guardian=1000, survivor=100, inspector=1000, watcher=1000
        # survivor needs 90 more for Gold, but span needs more
        # Let's just push watcher and guardian to gold
        ach.record("span", count=90)        # total 100 → Silver
        ach.record("span", count=900)       # total 1000 → Gold
        
        # Now push guardian + inspector + survivor to gold
        ach.record("intercept", count=900)  # total 1000 → Gold
        ach.record("validate_pass", count=900)  # total 1000 → Gold
        ach.record("recover", count=90)     # total 100 → Gold
        
        # All 4 core should be at Gold now
        master = ach.achievements["ark_master"]
        assert master.is_maxed

    def test_json_output(self):
        ach = Achievements()
        ach.record("intercept", count=15)
        j = ach.to_json()
        assert "guardian" in j


# ═══════════════════════════════════════════════════════════════
# Integration test: Dashboard + Achievements + Core
# ═══════════════════════════════════════════════════════════════

class TestIntegration:
    def test_full_pipeline(self):
        """Simulate a real agent run with all ARK components."""
        dash = get_dashboard()
        ach = Achievements()
        guard = IdempotencyGuard()
        breaker = CircuitBreaker("test-cb", failure_threshold=2)
        validator = OutputValidator()
        trace = Trace("integration-test")

        @guard.wrap
        def my_tool(x: int) -> int:
            return x * 2

        # Normal call
        result = my_tool(5)
        assert result == 10
        dash.record(Event(ts=time.time(), kind="validate_pass", agent="test-agent",
                          score_snapshot=100.0))
        ach.record("validate_pass", agent="test-agent")

        # Duplicate call → intercepted
        my_tool(5)  # intercepted by guard
        dash.record(Event(ts=time.time(), kind="intercept", agent="test-agent",
                          score_snapshot=95.0))
        ach.record("intercept", agent="test-agent")

        # Verify dashboard state
        tm = dash.trust_monitor
        assert tm["idempotency"]["intercepts"] == 1
        assert tm["validation"]["passes"] == 1

        # Verify achievements progressed
        assert ach.achievements["inspector"].progress >= 1
        assert ach.achievements["guardian"].progress >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
