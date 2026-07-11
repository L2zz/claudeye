"""OpenAI Codex adapter: rollout session discovery and lenient parsing.

Codex CLI records each session as
``~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl`` (archived copies
under a sibling ``archived_sessions/``). Every line is a
``{timestamp, type, payload}`` envelope; activity lives in ``response_item``
records and token usage in periodic ``event_msg`` ``token_count`` events.
This module normalizes those onto domain Events.

Two Codex-specific concerns are handled here so the rest of the pipeline
stays agent-agnostic:

  Dual stream. Assistant text appears both as ``response_item`` (canonical
  model output) and echoed as ``event_msg`` (UI log). We take
  ``response_item`` as canonical and mine ``event_msg`` only for
  ``token_count`` and compaction, so nothing is double counted.

  Cumulative tokens. Codex does not attach usage to each message; it emits
  periodic ``token_count`` events whose ``total_token_usage`` is the running
  session total and ``last_token_usage`` the last turn. We map one turn onto
  one assistant Event. Verified against real data: ``total_tokens ==
  input_tokens + output_tokens`` with ``cached_input`` a subset of input and
  ``reasoning_output`` a subset of output, so the split below never double
  counts.

Forward-compat: upstream ships a catch-all record variant and grows the tag
set over time, so unknown record/response types are skipped, never raised.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from claudeye.domain import (
    Event,
    ParseWarning,
    SessionFile,
    ToolResultRecord,
    ToolUseCall,
    Usage,
)
from claudeye.ingest.timeutil import _parse_timestamp

#: Source tag stamped onto every Codex Event.
CODEX_SOURCE = "codex"

#: Cumulative token-usage fields carried in a token_count event.
_TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "output_tokens",
    "reasoning_output_tokens",
)


def iter_session_files(root: Path, project_filter: str | None = None) -> Iterator[SessionFile]:
    """Discover Codex rollout transcripts under a sessions root.

    Yields active transcripts under root (recursively, the date tree) and
    then archived copies under the sibling ``archived_sessions/``; a rollout
    present in both is yielded once, the active copy winning (archived
    duplicates are skipped by filename). Does not read file contents unless
    project_filter is set, in which case each file's session_meta cwd is
    peeked to honor the filter.

    Args:
      root: Codex sessions directory, typically ~/.codex/sessions.
      project_filter: Case-insensitive substring matched against a
        session's cwd; when given, only matching sessions are yielded.
    """
    if not root.is_dir():
        return
    needle = project_filter.lower() if project_filter else None
    seen: set[str] = set()
    active = sorted(root.rglob("rollout-*.jsonl"))
    archived_dir = root.parent / "archived_sessions"
    archived = sorted(archived_dir.glob("rollout-*.jsonl")) if archived_dir.is_dir() else []
    for path in [*active, *archived]:
        stem = path.stem
        if stem in seen:
            continue  # active copy already yielded; archived duplicate skipped
        seen.add(stem)
        # Peek the session_meta cwd so the project is fixed at discovery — like
        # Claude's project dir name — which lets the digest cache round-trip it
        # (the cache reconstructs Event.project from SessionFile.project).
        cwd = _peek_cwd(path)
        if needle is not None and (cwd is None or needle not in cwd.lower()):
            continue
        project = _project_slug(cwd) if cwd else CODEX_SOURCE
        yield SessionFile(project=project, session_id=stem, path=path)


def parse_transcript(session_file: SessionFile, warnings: list[ParseWarning]) -> Iterator[Event]:
    """Parse one Codex rollout into Events, never raising per line.

    Lenient by contract: undecodable or structurally surprising lines append
    a ParseWarning and are skipped; record types irrelevant to the analysis
    (messages, reasoning, task timing, the event_msg echo stream) are skipped
    without warning. Emits one assistant Event per token_count turn (carrying
    usage), one per tool call/result, and system Events for compaction.
    """
    file_label = str(session_file.path)
    try:
        handle = session_file.path.open("r", encoding="utf-8", errors="replace")
    except OSError as exc:
        warnings.append(ParseWarning(file_label, 0, f"unreadable file: {exc}"))
        return

    # project is fixed at discovery (SessionFile.project) so warm cache reads
    # reconstruct it; the parser only tracks cwd (for display) and model here.
    project = session_file.project
    cwd: str | None = None
    model: str | None = None
    prev_total: dict[str, Any] | None = None

    with handle:
        for line_no, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except ValueError as exc:
                warnings.append(ParseWarning(file_label, line_no, f"invalid JSON: {exc}"))
                continue
            if not isinstance(raw, dict):
                warnings.append(ParseWarning(file_label, line_no, "non-object line"))
                continue
            payload = raw.get("payload")
            if not isinstance(payload, dict):
                continue  # session-level lines with no payload carry nothing to extract
            rtype = raw.get("type")
            ptype = payload.get("type")

            # Session/turn context updates state only; the first cwd fixes the
            # project so a mid-session cwd change never splits the session.
            if rtype == "session_meta":
                meta_cwd = payload.get("cwd")
                if isinstance(meta_cwd, str) and meta_cwd:
                    cwd = meta_cwd
                continue
            if rtype == "turn_context":
                tc_cwd = payload.get("cwd")
                if cwd is None and isinstance(tc_cwd, str) and tc_cwd:
                    cwd = tc_cwd
                tc_model = payload.get("model")
                if isinstance(tc_model, str) and tc_model:
                    model = tc_model
                continue

            timestamp = _parse_timestamp(raw.get("timestamp"))
            uuid = f"{session_file.session_id}:{line_no}"
            try:
                if rtype == "response_item":
                    if ptype == "function_call":
                        event = _new_event(project, session_file, "assistant", timestamp, uuid, cwd)
                        cid = payload.get("call_id")
                        event.tool_uses.append(
                            ToolUseCall(
                                tool_use_id=cid if isinstance(cid, str) else None,
                                name=str(payload.get("name") or "unknown"),
                            )
                        )
                        yield event
                    elif ptype == "function_call_output":
                        event = _new_event(project, session_file, "user", timestamp, uuid, cwd)
                        cid = payload.get("call_id")
                        event.tool_results.append(
                            ToolResultRecord(
                                tool_use_id=cid if isinstance(cid, str) else None,
                                result_bytes=_output_bytes(payload.get("output")),
                            )
                        )
                        yield event
                    elif ptype == "web_search_call":
                        event = _new_event(project, session_file, "assistant", timestamp, uuid, cwd)
                        event.tool_uses.append(ToolUseCall(tool_use_id=None, name="web_search"))
                        yield event
                    elif ptype in ("compaction", "context_compaction", "compaction_trigger"):
                        event = _new_event(project, session_file, "system", timestamp, uuid, cwd)
                        event.compact_boundary = True
                        yield event
                    # message / reasoning / agent_message / others: skipped by design
                elif rtype == "event_msg":
                    if ptype == "token_count":
                        info = payload.get("info")
                        if isinstance(info, dict):
                            usage, prev_total = _turn_usage(info, prev_total)
                            if usage is not None and usage.total() > 0:
                                event = _new_event(
                                    project, session_file, "assistant", timestamp, uuid, cwd
                                )
                                event.model = model
                                event.usage = usage
                                yield event
                    elif ptype == "context_compacted":
                        event = _new_event(project, session_file, "system", timestamp, uuid, cwd)
                        event.compact_boundary = True
                        yield event
                    # agent_message / user_message / task_* : the echo stream, skipped
                # unknown record type: skipped (forward-compat)
            except Exception as exc:  # lenient contract: no line may kill the file
                warnings.append(ParseWarning(file_label, line_no, f"unexpected shape: {exc}"))


def _new_event(
    project: str,
    session_file: SessionFile,
    kind: str,
    timestamp: Any,
    uuid: str,
    cwd: str | None,
) -> Event:
    """Build a Codex Event with the shared provenance fields filled in."""
    return Event(
        project=project,
        session_id=session_file.session_id,
        kind=kind,
        timestamp=timestamp,
        source=CODEX_SOURCE,
        uuid=uuid,
        cwd=cwd,
    )


def _turn_usage(
    info: dict[str, Any], prev_total: dict[str, Any] | None
) -> tuple[Usage | None, dict[str, Any] | None]:
    """Return one turn's Usage from a token_count info block, plus new prev.

    Prefers last_token_usage — Codex's own per-turn vector, always
    non-negative and field-consistent, and (verified on a real corpus)
    summing to within ~1% of the session's final cumulative total. Falls
    back to the delta of the cumulative total_token_usage only when no
    per-turn vector is present, clamping per-field deltas at 0 so a
    mid-session reset never yields a negative counter. prev_total tracks the
    cumulative vector for that fallback. Returns (None, prev) when the block
    carries no usable usage.
    """
    total = info.get("total_token_usage")
    total = total if isinstance(total, dict) else None
    last = info.get("last_token_usage")
    if isinstance(last, dict):
        return _usage_from_fields(last), (total if total is not None else prev_total)
    if total is not None:
        if prev_total is None:
            return _usage_from_fields(total), total
        delta = {k: max(_int(total.get(k)) - _int(prev_total.get(k)), 0) for k in _TOKEN_FIELDS}
        return _usage_from_fields(delta), total
    return None, prev_total


def _usage_from_fields(u: dict[str, Any]) -> Usage:
    """Map a Codex token vector onto Usage without double counting.

    cached_input is a subset of input and reasoning_output a subset of
    output (verified against real data), so cached and reasoning are peeled
    out into their own counters and the remainders kept as plain input and
    output. cache_creation has no Codex equivalent and stays 0.
    """
    inp = _int(u.get("input_tokens"))
    cached = _int(u.get("cached_input_tokens"))
    out = _int(u.get("output_tokens"))
    reasoning = _int(u.get("reasoning_output_tokens"))
    return Usage(
        input_tokens=max(inp - cached, 0),
        output_tokens=max(out - reasoning, 0),
        cache_read_tokens=cached,
        cache_creation_tokens=0,
        reasoning_tokens=reasoning,
    )


def _int(value: Any) -> int:
    """Coerce a token field to int, treating non-numbers as 0."""
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def _output_bytes(output: Any) -> int:
    """Measure the serialized size of a function_call_output payload."""
    if output is None:
        return 0
    if isinstance(output, str):
        return len(output.encode("utf-8", errors="replace"))
    try:
        return len(json.dumps(output, ensure_ascii=False).encode("utf-8", errors="replace"))
    except (TypeError, ValueError):
        return 0


def _project_slug(cwd: str) -> str:
    """Encode an absolute cwd into a project slug (/ -> -), Claude-style.

    Keeps Codex sessions groupable the same way as Claude's project dirs;
    the real cwd rides along on each Event for display.
    """
    return cwd.replace("/", "-")


def _peek_cwd(path: Path) -> str | None:
    """Read a rollout's leading session_meta to recover its cwd, or None."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for _ in range(5):
                line = handle.readline()
                if not line:
                    break
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict) and record.get("type") == "session_meta":
                    payload = record.get("payload")
                    if isinstance(payload, dict) and isinstance(payload.get("cwd"), str):
                        return payload["cwd"]
    except OSError:
        return None
    return None
