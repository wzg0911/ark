"""
ARK Dashboard — Trust Monitor + Trace Explorer + Scoreboard
v0.3.0 — In-browser trust observability for AI agents.

Usage:
    from ark import Dashboard
    dash = Dashboard()
    # ... agents run ...
    print(dash.render())
"""

import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Event:
    """A single trust event."""
    ts: float
    kind: str       # 'intercept' | 'block' | 'trip' | 'recover' | 'validate_pass' | 'validate_fail' | 'span'
    agent: str
    detail: str = ""
    score_snapshot: float = 0.0


@dataclass
class Dashboard:
    """Unified dashboard aggregating all ARK trust signals."""

    agents: Dict[str, dict] = field(default_factory=lambda: defaultdict(dict))
    events: List[Event] = field(default_factory=list)
    _global_intercepts: int = 0
    _global_blocks: int = 0
    _global_trips: int = 0
    _global_recoveries: int = 0
    _global_validate_passes: int = 0
    _global_validate_fails: int = 0
    _global_spans: int = 0

    # ── ingestion ──────────────────────────────────────────────

    def record(self, event: Event) -> None:
        self.events.append(event)
        kind = event.kind
        if kind == 'intercept':
            self._global_intercepts += 1
        elif kind == 'block':
            self._global_blocks += 1
        elif kind == 'trip':
            self._global_trips += 1
        elif kind == 'recover':
            self._global_recoveries += 1
        elif kind == 'validate_pass':
            self._global_validate_passes += 1
        elif kind == 'validate_fail':
            self._global_validate_fails += 1
        elif kind == 'span':
            self._global_spans += 1

        agent = event.agent
        if agent not in self.agents:
            self.agents[agent] = {
                "name": agent,
                "intercepts": 0,
                "blocks": 0,
                "trips": 0,
                "recoveries": 0,
                "validate_passes": 0,
                "validate_fails": 0,
                "spans": 0,
                "scores": [],
            }
        a = self.agents[agent]
        cap = {  # kind → counter key
            "intercept": "intercepts",
            "block": "blocks",
            "trip": "trips",
            "recover": "recoveries",
            "validate_pass": "validate_passes",
            "validate_fail": "validate_fails",
            "span": "spans",
        }
        if kind in cap:
            a[cap[kind]] += 1
        a["scores"].append(event.score_snapshot)

    # ── Trust Monitor ──────────────────────────────────────────

    @property
    def trust_monitor(self) -> Dict:
        total_checks = self._global_validate_passes + self._global_validate_fails
        pass_rate = (
            round(self._global_validate_passes / total_checks * 100, 1)
            if total_checks > 0
            else 100.0
        )
        return {
            "idempotency": {
                "intercepts": self._global_intercepts,
                "status": "🟢" if self._global_intercepts > 0 else "⚪",
            },
            "circuit_breaker": {
                "trips": self._global_trips,
                "recoveries": self._global_recoveries,
                "status": "🟢" if self._global_trips == 0 else "🟡",
            },
            "validation": {
                "passes": self._global_validate_passes,
                "fails": self._global_validate_fails,
                "pass_rate": pass_rate,
                "status": "🟢" if pass_rate >= 99 else "🟡" if pass_rate >= 90 else "🔴",
            },
            "trace": {
                "total_spans": self._global_spans,
                "status": "🟢" if self._global_spans > 0 else "⚪",
            },
        }

    @property
    def trust_monitor_text(self) -> str:
        m = self.trust_monitor
        return (
            "┌─────────────────────────────────────────────────┐\n"
            "│          🛡 ARK Trust Monitor                   │\n"
            "├─────────────────────────────────────────────────┤\n"
            f"│ Idempotency  │ {m['idempotency']['intercepts']:>6d} intercepts     {m['idempotency']['status']} │\n"
            f"│ Circuit Brkr │ {m['circuit_breaker']['trips']:>6d} trips         {m['circuit_breaker']['status']} │\n"
            f"│ Validation   │ {m['validation']['pass_rate']:>6.1f}% pass rate   {m['validation']['status']} │\n"
            f"│ Trace        │ {m['trace']['total_spans']:>6d} spans         {m['trace']['status']} │\n"
            "└─────────────────────────────────────────────────┘"
        )

    # ── Agent Scoreboard ───────────────────────────────────────

    @property
    def scoreboard(self) -> List[Dict]:
        board = []
        for name, data in self.agents.items():
            total = data["intercepts"] + data["blocks"] + data["validate_passes"] + data["validate_fails"]
            avg_score = (
                round(sum(data["scores"]) / len(data["scores"]), 1)
                if data["scores"]
                else 0
            )
            board.append({
                "agent": name,
                "intercepts": data["intercepts"],
                "blocks": data["blocks"],
                "trips": data["trips"],
                "avg_reliability": avg_score,
                "total_events": total,
            })
        board.sort(key=lambda x: x["avg_reliability"], reverse=True)
        return board

    @property
    def scoreboard_text(self) -> str:
        board = self.scoreboard
        if not board:
            return "No agents tracked yet."
        lines = [
            "┌──────────────────────────────────────────────────────────────┐",
            "│  🏆 Agent Reliability Scoreboard                           │",
            "├──────┬────────────┬────────┬───────┬────────────┬──────────┤",
            "│ Rank │ Agent      │ Interc.│ Blocks│ Trips      │ Score    │",
            "├──────┼────────────┼────────┼───────┼────────────┼──────────┤",
        ]
        medals = ["🥇", "🥈", "🥉"]
        for i, b in enumerate(board):
            m = medals[i] if i < 3 else f" {i+1} "
            lines.append(
                f"│ {m}  │ {b['agent']:<10} │ {b['intercepts']:>6} │ {b['blocks']:>5} │ {b['trips']:>10} │ {b['avg_reliability']:>7.1f}% │"
            )
        lines.append("└──────┴────────────┴────────┴───────┴────────────┴──────────┘")
        return "\n".join(lines)

    # ── Trace Explorer ─────────────────────────────────────────

    @property
    def trace_explorer(self) -> Dict:
        span_events = [e for e in self.events if e.kind == "span"]
        return {
            "total_spans": len(span_events),
            "agents_tracked": len(self.agents),
            "latest_10": [
                {"ts": e.ts, "agent": e.agent, "detail": e.detail}
                for e in span_events[-10:]
            ],
        }

    @property
    def trace_explorer_text(self) -> str:
        te = self.trace_explorer
        lines = [
            "┌──────────────────────────────────────────┐",
            "│  👁 Trace Explorer                      │",
            f"│  Total Spans: {te['total_spans']:<5}   Agents: {te['agents_tracked']:<5}          │",
            "├──────────────────────────────────────────┤",
        ]
        for e in te["latest_10"]:
            lines.append(f"│  {e['agent']:<12} {e['detail'][:26]:<26} │")
        lines.append("└──────────────────────────────────────────┘")
        return "\n".join(lines)

    # ── full render ────────────────────────────────────────────

    def render(self) -> str:
        return (
            f"{self.trust_monitor_text}\n\n"
            f"{self.scoreboard_text}\n\n"
            f"{self.trace_explorer_text}"
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "trust_monitor": self.trust_monitor,
                "scoreboard": self.scoreboard,
                "trace_explorer": self.trace_explorer,
            },
            indent=2,
            default=str,
        )


# ── singleton convenience ──────────────────────────────────────

_global_dashboard: Optional[Dashboard] = None


def get_dashboard() -> Dashboard:
    global _global_dashboard
    if _global_dashboard is None:
        _global_dashboard = Dashboard()
    return _global_dashboard
