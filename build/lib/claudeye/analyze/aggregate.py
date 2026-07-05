"""Pure aggregation of Events into per-session and daily read models.

analyze_events folds a stream of domain Events into SessionStats plus the
daily token matrix. All corpus-wide deduplication lives here (fork/continue
copies lines verbatim), so counting stays correct. No I/O.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from claudeye.domain import AnalysisResult, Event, SessionStats, SkillChainStats, Usage
from claudeye.ingest import SYNTHETIC_MODEL


def analyze_events(
    events: Iterable[Event],
    since: datetime | None = None,
) -> AnalysisResult:
    """Fold Events into per-session stats plus the daily token matrix.

    Pure aggregation: no I/O, no ordering assumptions beyond tool_use
    lines preceding their tool_result within one transcript. All
    deduplication lives here, in one global typed seen-set, because
    session fork/continue copies historical lines verbatim into the new
    session file (uuid included) — measured on a real corpus, per-session
    counting inflated tokens 8x and tool calls 6x:

      ("line", uuid)        one count per physical line corpus-wide; a
                            forked session therefore reports only the
                            activity that actually happened in it, and
                            inherited history stays with the file that
                            sorts first in discovery order.
      ("msg", message_id)   a streamed assistant message spans several
                            lines (distinct uuids) repeating one usage
                            block; marked seen only once usage was
                            consumed so a usage-less snapshot cannot
                            shadow a later usage-bearing one.
      ("use"/"res", tool_use_id)  defensive layer against repeated
                            tool_use/tool_result blocks; also keeps the
                            id -> tool name join global so a result can
                            resolve its name across copies.

    Tool results whose id never matched a tool_use fall into the
    reserved name (unmatched).

    Args:
      events: Normalized events from any number of transcript files.
      since: When given, events at or after this instant are kept; events
        older or without a timestamp are dropped, and sessions left with
        nothing are absent from the result.
    """
    sessions: dict[str, SessionStats] = {}
    day_usage: dict[tuple[str, str], Usage] = {}
    seen: set = set()
    tool_names_by_id: dict[str, str] = {}
    subagent_type_by_use: dict[str, str] = {}
    agent_types: dict[str, str] = {}
    pending_agent_links: list[tuple[str, str]] = []
    skill_chains: dict[str, SkillChainStats] = {}
    skill_by_use: dict[str, str] = {}

    for event in events:
        if since is not None and (event.timestamp is None or event.timestamp < since):
            continue
        if event.uuid is not None:
            line_key = ("line", event.uuid)
            if line_key in seen:
                continue
            seen.add(line_key)
        session_key = f"{event.project}/{event.session_id}"
        stats = sessions.get(session_key)
        if stats is None:
            stats = sessions[session_key] = SessionStats(
                project=event.project, session_id=event.session_id
            )
        context = event.agent_id or "main"

        if event.timestamp is not None:
            if stats.first_ts is None or event.timestamp < stats.first_ts:
                stats.first_ts = event.timestamp
            if stats.last_ts is None or event.timestamp > stats.last_ts:
                stats.last_ts = event.timestamp

        if event.agent_id:
            stats.subagent_ids.add(event.agent_id)

        skill = event.attribution_skill
        chain = None
        if skill is not None:
            chain = skill_chains.get(skill)
            if chain is None:
                chain = skill_chains[skill] = SkillChainStats()
        if event.kind == "assistant":
            _fold_assistant(event, stats, seen, day_usage, chain)
        if event.tool_uses:
            for call in event.tool_uses:
                if call.tool_use_id:
                    use_key = ("use", call.tool_use_id)
                    if use_key in seen:
                        continue
                    seen.add(use_key)
                    tool_names_by_id[call.tool_use_id] = call.name
                    if call.subagent_type:
                        subagent_type_by_use[call.tool_use_id] = call.subagent_type
                    if skill is not None:
                        skill_by_use[call.tool_use_id] = skill
                stats.tool_calls[call.name] += 1
                if chain is not None:
                    chain.tool_calls[call.name] += 1
                if call.name == "Read" and call.file_path:
                    stats.reads_by_context_path[(context, call.file_path)] += 1
        if event.tool_results:
            for result in event.tool_results:
                name = "(unmatched)"
                if result.tool_use_id:
                    res_key = ("res", result.tool_use_id)
                    if res_key in seen:
                        continue
                    seen.add(res_key)
                    name = tool_names_by_id.get(result.tool_use_id, "(unmatched)")
                    owner_skill = skill_by_use.get(result.tool_use_id)
                    if owner_skill is not None:
                        skill_chains[owner_skill].tool_result_bytes[name] += result.result_bytes
                stats.tool_result_bytes[name] += result.result_bytes
                if result.result_bytes > stats.tool_result_max_bytes[name]:
                    stats.tool_result_max_bytes[name] = result.result_bytes
                if result.is_error:
                    stats.tool_errors[name] += 1
        if event.agent_link is not None:
            use_id, agent_id = event.agent_link
            dispatch_type = subagent_type_by_use.get(use_id)
            if dispatch_type is not None:
                agent_types[agent_id] = dispatch_type
            else:
                # Sidechain files can be discovered before the dispatching
                # transcript; resolve these links once all events are seen.
                pending_agent_links.append((use_id, agent_id))
        if event.kind == "system":
            if event.compact_boundary:
                stats.compactions += 1
                if event.compact_pre_tokens is not None:
                    stats.compact_pre_tokens.append(event.compact_pre_tokens)
            elif event.is_api_error:
                if event.retry_attempt is not None:
                    stats.retries += 1
                else:
                    stats.api_errors += 1

    for use_id, agent_id in pending_agent_links:
        dispatch_type = subagent_type_by_use.get(use_id)
        if dispatch_type is not None:
            agent_types[agent_id] = dispatch_type

    return AnalysisResult(
        sessions=sessions,
        day_usage=day_usage,
        agent_types=agent_types,
        skill_chains=skill_chains,
    )


def _fold_assistant(
    event: Event,
    stats: SessionStats,
    seen: set,
    day_usage: dict[tuple[str, str], Usage],
    skill_chain: SkillChainStats | None = None,
) -> None:
    """Fold one assistant Event into session and daily aggregates.

    Handles the two assistant subtleties in one place: synthetic error
    placeholders count as errors (deduplicated by line uuid upstream) and
    never as requests or tokens, and usage repeated across streamed lines
    of one message counts once — marked seen only after usage was
    actually consumed, so a usage-less snapshot cannot shadow a later
    usage-bearing line of the same message.
    """
    if event.is_api_error or event.model == SYNTHETIC_MODEL:
        stats.api_errors += 1
        return
    if event.usage is None:
        return
    if event.message_id is not None:
        message_key = ("msg", event.message_id)
        if message_key in seen:
            return
        seen.add(message_key)
    if event.agent_id:
        stats.subagent_requests += 1
        stats.subagent_usage += event.usage
        per_agent = stats.subagent_usage_by_agent.get(event.agent_id, Usage())
        stats.subagent_usage_by_agent[event.agent_id] = per_agent + event.usage
        stats.subagent_requests_by_agent[event.agent_id] += 1
    else:
        stats.requests += 1
        stats.usage += event.usage
    if skill_chain is not None:
        skill_chain.requests += 1
        skill_chain.usage += event.usage
    model = event.model or "(unknown)"
    stats.models[model] += 1
    if event.timestamp is not None:
        day = event.timestamp.astimezone().date().isoformat()
        day_usage[(day, model)] = day_usage.get((day, model), Usage()) + event.usage
