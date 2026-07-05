"""Aggregation accumulators and the analysis result.

These are the mutable read models the analyze layer builds up as it folds
Events. They are not value objects: they accumulate over a pass and are
then frozen into summary rows. The waste-flag thresholds live here because
they define what SessionStats considers noteworthy.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from claudeye.domain.usage import Usage

#: Waste-flag thresholds. Deliberately coarse: flags are attention
#: pointers, not verdicts. Rationale per flag:
#:   dup-read   — 3+ re-reads of one file in one session is beyond the
#:                occasional legitimate refresh after an edit.
#:   low-cache  — cache efficiency below 0.5 over 5+ requests means most
#:                of the context is re-sent uncached (pollution or churn).
#:   compacted  — any auto/manual compaction proves the context filled up.
#:   errors     — 3+ API errors or retries hint at systematic waste.
WASTE_DUP_READ_MIN = 3
WASTE_CACHE_EFF_MAX = 0.5
WASTE_CACHE_MIN_REQUESTS = 5
WASTE_ERRORS_MIN = 3


@dataclass
class SessionStats:
    """Accumulated facts about one session (main plus its subagents).

    Built incrementally by analyze_events, then frozen into a summary
    row. Sessions are identified by (project, session_id); subagent
    events fold into the same stats with their tokens also tracked
    separately in subagent_usage so the split stays visible.
    """

    project: str
    session_id: str
    first_ts: datetime | None = None
    last_ts: datetime | None = None
    models: Counter = field(default_factory=Counter)
    requests: int = 0
    subagent_requests: int = 0
    usage: Usage = field(default_factory=Usage)
    subagent_usage: Usage = field(default_factory=Usage)
    subagent_usage_by_agent: dict[str, Usage] = field(default_factory=dict)
    subagent_requests_by_agent: Counter = field(default_factory=Counter)
    subagent_ids: set = field(default_factory=set)
    tool_calls: Counter = field(default_factory=Counter)
    tool_result_bytes: Counter = field(default_factory=Counter)
    tool_result_max_bytes: Counter = field(default_factory=Counter)
    tool_errors: Counter = field(default_factory=Counter)
    reads_by_context_path: Counter = field(default_factory=Counter)
    compactions: int = 0
    compact_pre_tokens: list[int] = field(default_factory=list)
    api_errors: int = 0
    retries: int = 0

    def cache_efficiency(self) -> float | None:
        """Return cache_read / (input + cache_read) for the main conversation.

        Subagent usage is excluded on purpose: subagents run in separate
        context windows, so folding them in would blur the health signal
        of the conversation the user actually sits in. None when the
        session has no input at all (nothing to be efficient about).
        """
        denominator = self.usage.input_tokens + self.usage.cache_read_tokens
        if denominator <= 0:
            return None
        return self.usage.cache_read_tokens / denominator

    def dup_read_files(self) -> dict[str, int]:
        """Return file paths Read more than once within one context.

        Keys are file paths, values the read count summed over contexts
        (main conversation and each subagent separately) where that path
        was read at least twice. Reading the same file in two different
        contexts is not counted as a duplicate — those are independent
        context windows.
        """
        per_path: Counter = Counter()
        for (_context, path), count in self.reads_by_context_path.items():
            if count >= 2:
                per_path[path] += count
        return dict(per_path)

    def wasted_reads(self) -> int:
        """Count re-reads beyond the first per (context, path) pair."""
        return sum(count - 1 for count in self.reads_by_context_path.values() if count >= 2)

    def waste_flags(self) -> list[str]:
        """Derive attention flags from the thresholds documented above."""
        flags: list[str] = []
        if any(count >= WASTE_DUP_READ_MIN for count in self.reads_by_context_path.values()):
            flags.append("dup-read")
        efficiency = self.cache_efficiency()
        if (
            efficiency is not None
            and self.requests >= WASTE_CACHE_MIN_REQUESTS
            and efficiency < WASTE_CACHE_EFF_MAX
        ):
            flags.append("low-cache")
        if self.compactions > 0:
            flags.append("compacted")
        if self.api_errors + self.retries >= WASTE_ERRORS_MIN:
            flags.append("errors")
        return flags


@dataclass
class SkillChainStats:
    """Downstream cost of one skill across the corpus.

    Counts whole assistant turns the harness stamped with the skill
    (attributionSkill) — tokens are grouped by turn, never split across
    tools, so this stays measured. Tool calls made on stamped turns and
    their result bytes (joined via tool_use_id) form the chain profile.
    """

    usage: Usage = field(default_factory=Usage)
    requests: int = 0
    tool_calls: Counter = field(default_factory=Counter)
    tool_result_bytes: Counter = field(default_factory=Counter)


@dataclass
class AnalysisResult:
    """Everything analyze_events extracts, ready for build_summary.

    sessions maps a project/session-id key to its stats; day_usage keeps
    the (local date, model) token matrix that cannot be reconstructed
    from per-session totals and feeds the daily stacked-bar chart.
    agent_types maps sidechain agent ids to their dispatch subagent_type,
    joined through toolUseResult.agentId (measured; ids that never joined
    stay absent and surface as unattributed downstream). skill_chains
    accumulates per-skill downstream cost from attributionSkill stamps.
    """

    sessions: dict[str, SessionStats]
    day_usage: dict[tuple[str, str], Usage]
    agent_types: dict[str, str] = field(default_factory=dict)
    skill_chains: dict[str, SkillChainStats] = field(default_factory=dict)
