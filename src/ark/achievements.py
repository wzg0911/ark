"""
ARK Achievements — Gamification engine for agent trust
v0.3.0 — Unlock badges as your agents become more reliable.

Usage:
    from ark import Achievements
    ach = Achievements()
    ach.record("intercept", agent="checkout-bot")
    ach.record("validate_pass", agent="checkout-bot")
    print(ach.summary())
"""

import time
from typing import Dict, List, Set
from dataclasses import dataclass, field
from enum import Enum


class Tier(Enum):
    BRONZE = ("🥉", 1)
    SILVER = ("🥈", 2)
    GOLD = ("🥇", 3)
    PLATINUM = ("💎", 4)

    def __init__(self, emoji: str, level: int):
        self.emoji = emoji
        self.level = level


@dataclass
class Achievement:
    id: str
    name: str
    description: str
    icon: str
    progress: int = 0           # current count
    target: int = 1             # count needed
    tiers: List[Tier] = field(default_factory=lambda: [Tier.BRONZE, Tier.SILVER, Tier.GOLD, Tier.PLATINUM])
    unlocked_at: List[float] = field(default_factory=list)  # timestamps of unlocks
    _previous_tier: int = 0

    @property
    def current_tier(self) -> Tier:
        return self.tiers[min(len(self.unlocked_at), len(self.tiers) - 1)]

    @property
    def is_maxed(self) -> bool:
        return len(self.unlocked_at) >= len(self.tiers)

    @property
    def next_tier_target(self) -> int:
        """Target for the next tier, or -1 if maxed."""
        if self.is_maxed:
            return -1
        idx = len(self.unlocked_at)
        multiplier_map = {0: 1, 1: 10, 2: 100, 3: 1000}
        return self.target * multiplier_map.get(idx, self.target)

    def progress_pct(self) -> float:
        if self.is_maxed:
            return 100.0
        return min(100.0, round(self.progress / self.next_tier_target * 100, 1))


# ── Predefined Achievements ────────────────────────────────────

ACHIEVEMENTS = {
    "guardian": Achievement(
        id="guardian",
        name="Guardian",
        icon="🛡",
        description="Intercept duplicate calls",
        target=10,  # Bronze at 10, Silver at 100, Gold at 1000, Platinum at 10000
    ),
    "survivor": Achievement(
        id="survivor",
        name="Survivor",
        icon="⚡",
        description="Circuit breaker recovers",
        target=1,   # Bronze at 1, Silver at 10, Gold at 100, Platinum at 1000
    ),
    "inspector": Achievement(
        id="inspector",
        name="Inspector",
        icon="🔧",
        description="Validations passed",
        target=10,  # Bronze at 10, Silver at 100, Gold at 1000, Platinum at 10000
    ),
    "watcher": Achievement(
        id="watcher",
        name="Watcher",
        icon="👁",
        description="Spans traced",
        target=10,  # Bronze at 10, Silver at 100, Gold at 1000, Platinum at 10000
    ),
    "ark_master": Achievement(
        id="ark_master",
        name="ARK Master",
        icon="🎖",
        description="All four achievements at Gold+",
        target=1,
        tiers=[Tier.PLATINUM],  # one-time ultimate unlock
    ),
}


@dataclass
class Achievements:
    """Tracks agent achievements and triggers unlocks."""

    achievements: Dict[str, Achievement] = field(
        default_factory=lambda: {k: Achievement(**v.__dict__) for k, v in ACHIEVEMENTS.items()}
    )
    recent_unlocks: List[Dict] = field(default_factory=list)  # push notifications

    # ── recording ──────────────────────────────────────────────

    def record(self, kind: str, agent: str = "default", count: int = 1) -> List[str]:
        """Record an event that may unlock achievements. Returns list of just-unlocked IDs."""
        unlocked = []

        mapping = {
            "intercept": "guardian",
            "recover": "survivor",
            "validate_pass": "inspector",
            "span": "watcher",
        }

        ach_id = mapping.get(kind)
        if not ach_id:
            return unlocked

        ach = self.achievements[ach_id]
        ach.progress += count

        # Try to unlock next tier
        while not ach.is_maxed:
            target = ach.next_tier_target
            if ach.progress >= target:
                ach.unlocked_at.append(time.time())
                tier_emoji = ach.current_tier.emoji
                tier_name = ach.current_tier.name
                self.recent_unlocks.append({
                    "achievement": ach.name,
                    "tier": tier_name,
                    "emoji": f"{ach.icon} {tier_emoji}",
                    "agent": agent,
                    "ts": ach.unlocked_at[-1],
                })
                unlocked.append(f"{ach.icon} {tier_emoji} {ach.name} ({tier_name}) — {agent}")
            else:
                break

        # Check ARK Master (all 4 at Gold+)
        core = ["guardian", "survivor", "inspector", "watcher"]
        master = self.achievements["ark_master"]
        if not master.is_maxed:
            all_gold = all(
                len(self.achievements[a].unlocked_at) >= 3 for a in core
            )
            if all_gold:
                master.progress = 1
                master.unlocked_at.append(time.time())
                self.recent_unlocks.append({
                    "achievement": "ARK Master",
                    "tier": "PLATINUM",
                    "emoji": "🎖 💎",
                    "agent": agent,
                    "ts": master.unlocked_at[-1],
                })
                unlocked.append("🎖 💎 ARK Master — ALL CORE ACHIEVEMENTS UNLOCKED!")

        return unlocked

    # ── rendering ───────────────────────────────────────────────

    @property
    def summary(self) -> List[Dict]:
        return [
            {
                "id": ach.id,
                "name": ach.name,
                "icon": ach.icon,
                "progress": ach.progress,
                "next_target": ach.next_tier_target,
                "progress_pct": ach.progress_pct(),
                "tier": f"{ach.current_tier.emoji} {ach.current_tier.name}" if ach.unlocked_at else "🔒 Locked",
                "unlocked_at": ach.unlocked_at.copy() if ach.unlocked_at else [],
                "maxed": ach.is_maxed,
            }
            for ach in self.achievements.values()
        ]

    def render(self) -> str:
        lines = [
            "┌──────────────────────────────────────────────────────────┐",
            "│  🏆 ARK Achievements                                    │",
            "├────────────────────┬──────────┬───────────┬────────────┤",
            "│ Achievement        │ Progress │ Progress  │ Tier       │",
            "├────────────────────┼──────────┼───────────┼────────────┤",
        ]
        for s in self.summary:
            pct = f"{s['progress_pct']}%"
            tier = s["tier"]
            bar = _progress_bar(s["progress_pct"])
            lines.append(
                f"│ {s['icon']} {s['name']:<16} │ {s['progress']:>8} │ {bar:<9} │ {tier:<10} │"
            )
        lines.append("└────────────────────┴──────────┴───────────┴────────────┘")

        if self.recent_unlocks:
            lines.append("\n🎉 Recent Unlocks:")
            for u in self.recent_unlocks[-5:]:
                lines.append(f"   {u['emoji']} {u['achievement']} ({u['tier']})")

        return "\n".join(lines)

    def to_json(self) -> str:
        import json
        return json.dumps(self.summary, indent=2, default=str)


def _progress_bar(pct: float, width: int = 8) -> str:
    filled = int(pct / 100 * width)
    empty = width - filled
    return "█" * filled + "░" * empty
