"""
ARK Reliability Score — 病毒传播基因 🎮
每个Agent运行后自动评分，可分享到社交媒体
"""

from dataclasses import dataclass, field
from typing import Dict, List
import time


@dataclass
class ReliabilityScore:
    """Agent可靠性评分引擎"""
    
    total_runs: int = 0
    successful_runs: int = 0
    duplicate_intercepts: int = 0
    output_blocks: int = 0
    circuit_trips: int = 0
    total_tool_calls: int = 0
    total_tool_failures: int = 0
    scores_history: List[Dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    
    @property
    def score(self) -> float:
        if self.total_runs == 0:
            return 0
        base = (self.successful_runs / self.total_runs) * 100
        penalty = (self.duplicate_intercepts + self.output_blocks) * 0.3
        failure_penalty = (self.total_tool_failures / max(self.total_tool_calls, 1)) * 15
        return max(0, min(100, round(base - penalty - failure_penalty, 1)))
    
    @property
    def grade(self) -> str:
        s = self.score
        if s >= 97: return "S+ 🏆"
        if s >= 93: return "S"
        if s >= 85: return "A+"
        if s >= 80: return "A"
        if s >= 70: return "B+"
        if s >= 60: return "B"
        if s >= 50: return "C"
        return "D"
    
    @property
    def badge_url(self) -> str:
        """生成可分享的Badge"""
        colors = {
            "S+ 🏆": "FFD700", "S": "00C853", "A+": "4CAF50",
            "A": "8BC34A", "B+": "FFC107", "B": "FF9800",
            "C": "FF5722", "D": "F44336"
        }
        color = colors.get(self.grade, "999")
        return f"https://img.shields.io/badge/ARK_Score-{self.score}%25_{self.grade.replace(' ','_')}-{color}?style=for-the-badge&logo=shield"
    
    @property
    def markdown_badge(self) -> str:
        return f"[![ARK Score]({self.badge_url})](https://github.com/wzg0911/ark)"
    
    @property
    def share_text(self) -> str:
        """自动生成社交媒体分享文案"""
        templates = {
            "S+ 🏆": f"🔥 Just hit {self.score}% reliability on my AI agents! ARK caught {self.duplicate_intercepts} duplicates & {self.output_blocks} errors. My agent is S+ tier now. {self.markdown_badge}",
            "S": f"⚡ Agent reliability: {self.score}% (S rank). ARK = trust infrastructure for AI. {self.markdown_badge}",
            "A+": f"📈 My AI agent is A+ ({self.score}%). Getting closer to perfect. ARK makes agents trustworthy. {self.markdown_badge}",
            "B+": f"🔧 Agent at {self.score}% — ARK found {self.duplicate_intercepts} dupes. Getting better every run. {self.markdown_badge}",
        }
        return templates.get(self.grade, f"🛡 Agent trust: {self.score}%. {self.duplicate_intercepts} safe intercepts. {self.markdown_badge}")
    
    def record_run(self, success: bool, intercepts: int = 0, blocks: int = 0, 
                   tool_calls: int = 0, tool_failures: int = 0, circuit_trips: int = 0):
        self.total_runs += 1
        if success: self.successful_runs += 1
        self.duplicate_intercepts += intercepts
        self.output_blocks += blocks
        self.total_tool_calls += tool_calls
        self.total_tool_failures += tool_failures
        self.circuit_trips += circuit_trips
        
        self.scores_history.append({
            "timestamp": time.time(),
            "score": self.score,
            "grade": self.grade,
            "intercepts": intercepts,
        })
    
    @property
    def summary(self) -> Dict:
        return {
            "score": self.score,
            "grade": self.grade,
            "total_runs": self.total_runs,
            "success_rate": f"{(self.successful_runs/max(self.total_runs,1))*100:.1f}%",
            "total_intercepts": self.duplicate_intercepts,
            "total_blocks": self.output_blocks,
            "tool_reliability": f"{(1 - self.total_tool_failures/max(self.total_tool_calls,1))*100:.1f}%",
            "badge": self.markdown_badge,
            "share": self.share_text,
        }
    
    def comparison(self, before_scores: Dict = None) -> str:
        """生成Before/After对比表"""
        before = before_scores or {
            "duplicate_calls": self.duplicate_intercepts,
            "crashes": self.total_tool_failures,
            "invalid_outputs": self.output_blocks,
            "trust": "?",
        }
        return f"""
┌──────────────────┬────────────┬────────────┐
│ Metric           │ Without ARK│ With ARK   │
├──────────────────┼────────────┼────────────┤
│ Duplicate calls  │     {before.get('duplicate_calls', '?')}      │     {max(0, self.duplicate_intercepts - before.get('duplicate_calls', self.duplicate_intercepts))}       │
│ Agent crashes    │     {before.get('crashes', '?')}      │     {max(0, self.total_tool_failures - before.get('crashes', self.total_tool_failures))}       │
│ Invalid outputs  │     {before.get('invalid_outputs', '?')}      │     {max(0, self.output_blocks - before.get('invalid_outputs', self.output_blocks))}       │
│ Trust score      │    {before.get('trust', '?')}%    │    {self.score}%    │
├──────────────────┼────────────┼────────────┤
│ Status           │ 🔴 Vulnerable│ 🟢 Protected │
└──────────────────┴────────────┴────────────┘"""
