"""Advice configuration and severity levels.

AdviceConfig is the tunable value object that drives the advice rules;
its defaults are the codex-converged thresholds. Severity is ordered like
log levels (info < warn < critical). The rule-firing logic itself lives in
the analyze layer; only the config and level vocabulary are domain.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


@dataclass(frozen=True)
class AdviceConfig:
    """Tunable thresholds for the advice rules.

    Defaults are the codex-converged values. A personal config file
    (~/.config/claudeye/config.json, or --config PATH) can override any
    field, so tuned thresholds persist across runs. The rule definitions
    and the report's what-if panel both read these, so the definition
    text, the firing logic, and the config never drift.

    Rationale for the defaults (deliberately conservative so the advice
    section stays short and trustworthy): a file re-read 20+ wasted times
    across 3+ sessions is a standing knowledge gap; 2+ compactions in one
    session means the context filled twice; low cache only matters as a
    pattern (>25% of 4+ rated sessions); a 200 KB result pollutes context
    in one shot; a skill needs 40k+ new tokens/turn over 10+ turns (real
    corpus: new-spend/turn median 7k, p90 37k) so a tiny sample cannot
    trip it. new-spend excludes cache reads — those reflect session
    fatness, not the skill's own cost.
    """

    dup_wasted_min: int = 20
    dup_sessions_min: int = 3
    compactions_min: int = 2
    low_cache_share: float = 0.25
    low_cache_min_sessions: int = 4
    result_bytes_min: int = 200_000
    skill_min_turns: int = 10
    skill_new_spend_per_turn: int = 40_000
    skill_result_bytes_per_turn: int = 100_000
    skill_fanout_per_turn: int = 8
    # Absolute critical-escalation thresholds (an item speaks louder past
    # these, like WARN -> ERROR). Defaults preserve the old 2x/3x cuts.
    dup_critical_wasted: int = 60
    compactions_critical: int = 4
    result_bytes_critical: int = 400_000
    skill_critical_new_spend_per_turn: int = 80_000
    max_items: int = 5

    @classmethod
    def from_dict(cls, data: Any) -> AdviceConfig:
        """Build a config from a dict, keeping defaults for absent keys.

        Accepts either a flat mapping or one nested under an "advice"
        key. Unknown keys and wrong-typed values are ignored so a typo
        degrades to the default, never a crash.
        """
        section = data.get("advice", data) if isinstance(data, dict) else None
        if not isinstance(section, dict):
            return cls()
        defaults = cls()
        overrides: dict[str, Any] = {}
        for f in fields(cls):
            value = section.get(f.name)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                overrides[f.name] = type(getattr(defaults, f.name))(value)
        return cls(**overrides)


#: Advice severity ordered like log levels: info < warn < critical.
#: Each rule has a base level; an item escalates to critical when its
#: primary metric runs far past the threshold (a magnitude escalation,
#: like ERROR vs WARN), so the same rule can speak at two volumes.
LEVEL_ORDER = ["info", "warn", "critical"]
ADVICE_BASE_LEVEL: dict[str, str] = {
    "dup-read-hotspot": "warn",
    "compaction-pressure": "warn",
    "low-cache-pattern": "info",
    "huge-tool-result": "warn",
    "skill-heavy-turns": "warn",
}
