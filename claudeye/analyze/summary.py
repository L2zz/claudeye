"""Freeze analysis read models into the JSON-serializable summary dict.

build_summary is the single contract between analyze and render (and the
--json artifact): it turns SessionStats, the daily matrix, and the advice
rules into one plain dict of aggregated numbers. File paths are home-
relativized and redactable; no other transcript text is carried over.
"""

from __future__ import annotations

import hashlib
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from claudeye import __version__ as VERSION
from claudeye.analyze.advice import _build_advice, advice_rule_catalog
from claudeye.domain import (
    AdviceConfig,
    AnalysisResult,
    ParseWarning,
    Usage,
)

CONFIDENCE_NOTES: dict[str, str] = {
    "tokens": "measured — usage deduplicated by line uuid and API message id, "
    "so history copied into forked/continued sessions counts once corpus-wide",
    "tool_calls": "measured — tool_use blocks counted once per tool_use_id",
    "tool_result_bytes": "measured — serialized tool_result payload re-entering context",
    "dup_reads": "inferred — Read tool file_path repeats only; cat/Grep re-reads not covered",
    "cache_efficiency": "measured — cache_read / (input + cache_read) per session",
    "fork_attribution": "inferred — a forked session reports only activity that "
    "happened in it; inherited history stays with the first-discovered sharing session",
    "subagent_types": "measured — sidechain tokens joined to dispatch subagent_type "
    "via toolUseResult.agentId; agents that never joined stay (unattributed), never guessed",
    "skill_chains": "measured — whole assistant turns stamped attributionSkill by the "
    "harness, grouped per skill (tokens are never split across tools); chained tool "
    "results joined via tool_use_id; turns outside any skill are simply not attributed",
    "per_tool_tokens": "approximate by design — usage is per API response; "
    "this tool deliberately does not attribute tokens to individual tools",
}


#: Hard cap on parse warnings carried into the summary artifact.
MAX_WARNINGS_IN_SUMMARY = 100

#: Hard cap on duplicate-read rows carried into the summary artifact.
MAX_DUP_READ_ROWS = 50


def _new_tokens(usage: Usage) -> int:
    """Return an attribution's own footprint: input + output + cache write.

    Cache reads are excluded on purpose. For a skill/agent (a slice of a
    turn, attributed by attributionSkill / agentId) the cache_read is
    ambient call-time context, and it is double-counted across every
    slice that fires in the same fat session — so it measures the session,
    not the slice. This is the same basis the skill-heavy-turns advice
    uses (new_spend/turn), keeping ranking and advice consistent.
    """
    return usage.input_tokens + usage.output_tokens + usage.cache_creation_tokens


def build_summary(
    result: AnalysisResult,
    parse_warnings: list[ParseWarning],
    *,
    input_root: str,
    since: datetime | None,
    project_filter: str | None,
    redact_paths: bool = False,
    generated_at: datetime | None = None,
    advice_config: AdviceConfig | None = None,
    config_source: str | None = None,
    lang: str = "en",
) -> dict[str, Any]:
    """Freeze analysis results into the JSON-serializable summary dict.

    This is the single contract between analyze and render (and the
    --json artifact). Top-level keys: meta (run parameters, confidence
    notes, warning count), totals, by_tool, by_day, sessions, dup_reads,
    parse_warnings (capped). File paths are home-relativized always and
    redacted to hashed-dir/basename when redact_paths is set; no other
    transcript text is carried over.
    """
    cfg = advice_config or AdviceConfig()
    home = str(Path.home())

    def clean_path(path: str) -> str:
        if path.startswith(home):
            path = "~" + path[len(home) :]
        return _redact_path(path) if redact_paths else path

    # Encoded project slugs (-Users-me-my-project) can't be decoded
    # back to a path unambiguously (hyphens in names collide with separators),
    # so display the session's real cwd instead — home-relativized and redacted
    # the same as any other path. Fall back to the slug when no cwd was seen.
    project_cwd: dict[str, str] = {}
    for st in result.sessions.values():
        if st.cwd and st.project not in project_cwd:
            project_cwd[st.project] = st.cwd

    def clean_project(slug: str) -> str:
        cwd = project_cwd.get(slug)
        if cwd:
            return clean_path(cwd)
        if not redact_paths:
            return slug
        tail = slug.rsplit("-", 1)[-1] or "project"
        digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
        return f"{digest}…{tail}"

    def iso(value: datetime | None) -> str | None:
        return value.isoformat(timespec="seconds") if value else None

    session_rows: list[dict[str, Any]] = []
    tool_rows: dict[str, dict[str, int]] = {}
    dup_by_path: dict[str, dict[str, Any]] = {}
    project_rows: dict[str, dict[str, Any]] = {}
    totals_usage = Usage()
    totals = {
        "sessions": 0,
        "projects": 0,
        "requests": 0,
        "subagent_requests": 0,
        "tool_calls": 0,
        "tool_result_bytes": 0,
        "wasted_reads": 0,
        "compactions": 0,
        "errors": 0,
    }
    projects_seen = set()

    for stats in result.sessions.values():
        combined = stats.usage + stats.subagent_usage
        totals_usage += combined
        projects_seen.add(stats.project)
        totals["sessions"] += 1
        totals["requests"] += stats.requests
        totals["subagent_requests"] += stats.subagent_requests
        totals["tool_calls"] += sum(stats.tool_calls.values())
        totals["tool_result_bytes"] += sum(stats.tool_result_bytes.values())
        totals["wasted_reads"] += stats.wasted_reads()
        totals["compactions"] += stats.compactions
        totals["errors"] += stats.api_errors + stats.retries

        proj = project_rows.setdefault(
            stats.project,
            {
                "sessions": 0,
                "requests": 0,
                "subagent_requests": 0,
                "main_usage": Usage(),
                "combined_usage": Usage(),
                "tool_calls": 0,
                "tool_result_bytes": 0,
                "wasted_reads": 0,
                "compactions": 0,
                "errors": 0,
            },
        )
        proj["sessions"] += 1
        proj["requests"] += stats.requests
        proj["subagent_requests"] += stats.subagent_requests
        proj["main_usage"] += stats.usage
        proj["combined_usage"] += combined
        proj["tool_calls"] += sum(stats.tool_calls.values())
        proj["tool_result_bytes"] += sum(stats.tool_result_bytes.values())
        proj["wasted_reads"] += stats.wasted_reads()
        proj["compactions"] += stats.compactions
        proj["errors"] += stats.api_errors + stats.retries

        for name in set(stats.tool_calls) | set(stats.tool_result_bytes):
            row = tool_rows.setdefault(
                name,
                {"calls": 0, "errors": 0, "result_bytes": 0, "max_result_bytes": 0},
            )
            row["calls"] += stats.tool_calls.get(name, 0)
            row["errors"] += stats.tool_errors.get(name, 0)
            row["result_bytes"] += stats.tool_result_bytes.get(name, 0)
            row["max_result_bytes"] = max(
                row["max_result_bytes"], stats.tool_result_max_bytes.get(name, 0)
            )

        session_dup_paths = set()
        for (_context, path), count in stats.reads_by_context_path.items():
            if count < 2:
                continue
            entry = dup_by_path.setdefault(
                path,
                {
                    "reads": 0,
                    "wasted_reads": 0,
                    "sessions": set(),
                    "max_in_one_context": 0,
                },
            )
            entry["reads"] += count
            entry["wasted_reads"] += count - 1
            entry["sessions"].add(stats.session_id)
            entry["max_in_one_context"] = max(entry["max_in_one_context"], count)
            session_dup_paths.add(path)

        efficiency = stats.cache_efficiency()
        duration_min: float | None = None
        if stats.first_ts and stats.last_ts:
            duration_min = round((stats.last_ts - stats.first_ts).total_seconds() / 60, 1)
        session_rows.append(
            {
                "project": clean_project(stats.project),
                "session_id": stats.session_id,
                "first_ts": iso(stats.first_ts),
                "last_ts": iso(stats.last_ts),
                "duration_min": duration_min,
                "models": [name for name, _ in stats.models.most_common()],
                "requests": stats.requests,
                "subagents": len(stats.subagent_ids),
                "subagent_requests": stats.subagent_requests,
                "input_tokens": combined.input_tokens,
                "output_tokens": combined.output_tokens,
                "cache_read_tokens": combined.cache_read_tokens,
                "cache_creation_tokens": combined.cache_creation_tokens,
                "total_tokens": combined.total(),
                "subagent_total_tokens": stats.subagent_usage.total(),
                "tool_calls": sum(stats.tool_calls.values()),
                "dup_read_files": len(session_dup_paths),
                "wasted_reads": stats.wasted_reads(),
                "compactions": stats.compactions,
                "compact_pre_tokens": stats.compact_pre_tokens,
                "errors": stats.api_errors + stats.retries,
                "cache_efficiency": round(efficiency, 4) if efficiency is not None else None,
                "flags": stats.waste_flags(),
            }
        )

    totals["projects"] = len(projects_seen)
    session_rows.sort(key=lambda row: row["total_tokens"], reverse=True)

    agent_type_rows: dict[str, dict[str, Any]] = {}
    for stats in result.sessions.values():
        for agent_id, usage in stats.subagent_usage_by_agent.items():
            type_name = result.agent_types.get(agent_id, "(unattributed)")
            agent_row = agent_type_rows.get(type_name)
            if agent_row is None:
                agent_row = agent_type_rows[type_name] = {
                    "agents": 0,
                    "requests": 0,
                    "usage": Usage(),
                }
            agent_row["agents"] += 1
            agent_row["requests"] += stats.subagent_requests_by_agent.get(agent_id, 0)
            agent_row["usage"] += usage
    by_agent_type: list[dict[str, Any]] = [
        {
            "type": type_name,
            "agents": agent_row["agents"],
            "requests": agent_row["requests"],
            "input_tokens": agent_row["usage"].input_tokens,
            "output_tokens": agent_row["usage"].output_tokens,
            "cache_read_tokens": agent_row["usage"].cache_read_tokens,
            "cache_creation_tokens": agent_row["usage"].cache_creation_tokens,
            "total_tokens": agent_row["usage"].total(),
            "new_tokens": _new_tokens(agent_row["usage"]),
        }
        for type_name, agent_row in agent_type_rows.items()
    ]
    # Attribution slices rank by new tokens (input + output + cache write),
    # NOT total: cache_read is ambient call-time context, double-counted
    # across every skill/agent that fires in a fat session, so it would
    # crown the peak-context regular (e.g. stage) over its real footprint.
    # This matches the skill-heavy-turns advice basis (new_spend/turn).
    by_agent_type.sort(key=lambda r: r["new_tokens"], reverse=True)

    by_skill_chain: list[dict[str, Any]] = []
    for skill_name, chain in result.skill_chains.items():
        tools = [
            {
                "name": name,
                "calls": calls,
                "result_bytes": chain.tool_result_bytes.get(name, 0),
            }
            for name, calls in chain.tool_calls.most_common()
        ]
        by_skill_chain.append(
            {
                "skill": skill_name,
                "requests": chain.requests,
                "input_tokens": chain.usage.input_tokens,
                "output_tokens": chain.usage.output_tokens,
                "cache_read_tokens": chain.usage.cache_read_tokens,
                "cache_creation_tokens": chain.usage.cache_creation_tokens,
                "total_tokens": chain.usage.total(),
                "new_tokens": _new_tokens(chain.usage),
                "tool_calls": sum(chain.tool_calls.values()),
                "tool_result_bytes": sum(chain.tool_result_bytes.values()),
                "tools": tools,
            }
        )
    # See the by_agent_type note above: attribution ranks by new tokens.
    by_skill_chain.sort(key=lambda row: row["new_tokens"], reverse=True)

    by_project: list[dict[str, Any]] = []
    for slug, proj in project_rows.items():
        main: Usage = proj["main_usage"]
        combined_usage: Usage = proj["combined_usage"]
        eff_denominator = main.input_tokens + main.cache_read_tokens
        by_project.append(
            {
                "project": clean_project(slug),
                "sessions": proj["sessions"],
                "requests": proj["requests"],
                "subagent_requests": proj["subagent_requests"],
                "input_tokens": combined_usage.input_tokens,
                "output_tokens": combined_usage.output_tokens,
                "cache_read_tokens": combined_usage.cache_read_tokens,
                "cache_creation_tokens": combined_usage.cache_creation_tokens,
                "total_tokens": combined_usage.total(),
                "cache_efficiency": (
                    round(main.cache_read_tokens / eff_denominator, 4)
                    if eff_denominator > 0
                    else None
                ),
                "tool_calls": proj["tool_calls"],
                "tool_result_bytes": proj["tool_result_bytes"],
                "wasted_reads": proj["wasted_reads"],
                "compactions": proj["compactions"],
                "errors": proj["errors"],
            }
        )
    by_project.sort(key=lambda row: row["total_tokens"], reverse=True)

    by_tool = [
        {"name": name, **row}
        for name, row in sorted(
            tool_rows.items(), key=lambda item: item[1]["result_bytes"], reverse=True
        )
    ]

    by_day = [
        {
            "date": day,
            "model": model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_tokens": usage.cache_read_tokens,
            "cache_creation_tokens": usage.cache_creation_tokens,
        }
        for (day, model), usage in sorted(result.day_usage.items())
    ]

    dup_reads = [
        {
            "path": clean_path(path),
            "reads": entry["reads"],
            "wasted_reads": entry["wasted_reads"],
            "sessions": len(entry["sessions"]),
            "max_in_one_context": entry["max_in_one_context"],
        }
        for path, entry in sorted(
            dup_by_path.items(),
            key=lambda item: (item[1]["wasted_reads"], item[1]["reads"]),
            reverse=True,
        )[:MAX_DUP_READ_ROWS]
    ]

    warning_rows = [
        {"file": clean_path(w.file), "line": w.line_no, "reason": w.reason}
        for w in parse_warnings[:MAX_WARNINGS_IN_SUMMARY]
    ]

    stamp = generated_at or datetime.now(timezone.utc)
    input_display = clean_path(input_root)
    return {
        "meta": {
            "tool": "claudeye",
            "version": VERSION,
            "generated_at": stamp.isoformat(timespec="seconds"),
            "input_root": input_display,
            "since": since.isoformat(timespec="seconds") if since else None,
            "project_filter": project_filter,
            "redact_paths": redact_paths,
            "lang": lang,
            "config_source": clean_path(config_source) if config_source else None,
            "parse_warnings_total": len(parse_warnings),
            "confidence": dict(CONFIDENCE_NOTES),
        },
        "totals": {
            **totals,
            "input_tokens": totals_usage.input_tokens,
            "output_tokens": totals_usage.output_tokens,
            "cache_read_tokens": totals_usage.cache_read_tokens,
            "cache_creation_tokens": totals_usage.cache_creation_tokens,
            "total_tokens": totals_usage.total(),
        },
        "by_tool": by_tool,
        "by_day": by_day,
        "by_project": by_project,
        "by_agent_type": by_agent_type,
        "by_skill_chain": by_skill_chain,
        "advice": _build_advice(session_rows, dup_reads, by_tool, by_skill_chain, cfg),
        "advice_rules": advice_rule_catalog(cfg),
        "advice_thresholds": {f.name: getattr(cfg, f.name) for f in fields(cfg)},
        "sessions": session_rows,
        "dup_reads": dup_reads,
        "parse_warnings": warning_rows,
    }


def _redact_path(path: str) -> str:
    """Replace a path's directory with a short stable hash, keep basename.

    Stable across runs so redacted reports remain diffable; the basename
    stays readable because it is what the user acts on (which file keeps
    getting re-read), while the directory is what identifies the machine
    or client.
    """
    pure = Path(path)
    name = pure.name or "path"
    digest = hashlib.sha1(str(pure.parent).encode("utf-8")).hexdigest()[:8]
    return f"…{digest}/{name}"
