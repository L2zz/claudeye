"""Filesystem discovery and lenient JSONL parsing.

The ingest layer turns a Claude Code projects directory into a stream of
normalized domain Events. It is lenient by contract: a corrupt line
becomes a ParseWarning, never an exception, so one bad line cannot
discard a whole session file. This module owns discovery
(iter_session_files) and per-line parsing (parse_transcript).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timezone
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

#: Alias layer for usage field names. Claude Code has historically emitted
#: snake_case; camelCase variants are accepted defensively so a schema drift
#: degrades into missing aliases, not silent zeros.
USAGE_ALIASES: dict[str, tuple[str, ...]] = {
    "input_tokens": ("input_tokens", "inputTokens"),
    "output_tokens": ("output_tokens", "outputTokens"),
    "cache_read_tokens": (
        "cache_read_input_tokens",
        "cacheReadInputTokens",
        "cache_read_tokens",
    ),
    "cache_creation_tokens": (
        "cache_creation_input_tokens",
        "cacheCreationInputTokens",
        "cache_creation_tokens",
    ),
}

#: Sentinel model name Claude Code uses for locally synthesized assistant
#: messages (API error placeholders). They carry no real usage.
SYNTHETIC_MODEL = "<synthetic>"


def iter_session_files(root: Path, project_filter: str | None = None) -> Iterator[SessionFile]:
    """Discover transcript files under a Claude Code projects root.

    Yields main session transcripts (project-dir/session-id.jsonl) and
    subagent transcripts (project-dir/session-id/subagents/agent-*.jsonl).
    Does not read file contents. Unknown files and directories are
    ignored silently — the projects root also hosts memory and
    tool-results side data that is out of scope here.

    Args:
      root: Projects directory, typically ~/.claude/projects.
      project_filter: Case-insensitive substring; when given, only
        project directories whose name contains it are yielded.
    """
    if not root.is_dir():
        return
    needle = project_filter.lower() if project_filter else None
    for project_dir in sorted(root.iterdir()):
        if not project_dir.is_dir():
            continue
        if needle is not None and needle not in project_dir.name.lower():
            continue
        for entry in sorted(project_dir.iterdir()):
            if entry.is_file() and entry.suffix == ".jsonl":
                yield SessionFile(
                    project=project_dir.name,
                    session_id=entry.stem,
                    path=entry,
                )
            elif entry.is_dir():
                subagents_dir = entry / "subagents"
                if not subagents_dir.is_dir():
                    continue
                for agent_file in sorted(subagents_dir.glob("agent-*.jsonl")):
                    yield SessionFile(
                        project=project_dir.name,
                        session_id=entry.name,
                        path=agent_file,
                        agent_id=agent_file.stem[len("agent-") :],
                    )


def parse_transcript(session_file: SessionFile, warnings: list[ParseWarning]) -> Iterator[Event]:
    """Parse one transcript file into Events, never raising per line.

    Lenient by contract: undecodable or structurally surprising lines
    append a ParseWarning and are skipped; line types irrelevant to the
    analysis (queue-operation, attachment, mode, ...) are skipped without
    warning; join keys and timestamps may come out None. I/O errors on
    the file itself also degrade into a single warning.

    Args:
      session_file: Discovered transcript to read.
      warnings: Shared sink the caller owns; parse problems are appended.
    """
    file_label = str(session_file.path)
    try:
        handle = session_file.path.open("r", encoding="utf-8", errors="replace")
    except OSError as exc:
        warnings.append(ParseWarning(file_label, 0, f"unreadable file: {exc}"))
        return
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
            kind = raw.get("type")
            if kind not in ("assistant", "user", "system"):
                continue  # queue-operation, attachment, mode, ... — irrelevant by design
            try:
                yield _line_to_event(raw, kind, session_file)
            except Exception as exc:  # lenient contract: no line may kill the file
                warnings.append(ParseWarning(file_label, line_no, f"unexpected shape: {exc}"))


def _line_to_event(raw: dict[str, Any], kind: str, session_file: SessionFile) -> Event:
    """Map one decoded transcript line onto an Event (see Event docstring)."""
    uuid = raw.get("uuid")
    event = Event(
        project=session_file.project,
        session_id=session_file.session_id,
        kind=kind,
        timestamp=_parse_timestamp(raw.get("timestamp")),
        uuid=uuid if isinstance(uuid, str) else None,
        agent_id=session_file.agent_id or raw.get("agentId"),
    )
    message = raw.get("message")
    message = message if isinstance(message, dict) else {}
    if kind == "assistant":
        event.message_id = message.get("id")
        skill = raw.get("attributionSkill")
        event.attribution_skill = skill if isinstance(skill, str) and skill else None
        event.model = message.get("model")
        event.usage = _normalize_usage(message.get("usage"))
        event.request_id = raw.get("requestId")
        event.is_api_error = bool(raw.get("isApiErrorMessage")) or event.model == SYNTHETIC_MODEL
        for block in _iter_blocks(message.get("content")):
            if block.get("type") == "tool_use":
                tool_input = block.get("input")
                subagent_type = None
                if isinstance(tool_input, dict) and isinstance(
                    tool_input.get("subagent_type"), str
                ):
                    subagent_type = tool_input["subagent_type"]
                event.tool_uses.append(
                    ToolUseCall(
                        tool_use_id=block.get("id"),
                        name=_tool_display_name(str(block.get("name") or "unknown"), tool_input),
                        file_path=_extract_file_path(tool_input),
                        subagent_type=subagent_type,
                    )
                )
    elif kind == "user":
        event.is_compact_summary = bool(raw.get("isCompactSummary"))
        for block in _iter_blocks(message.get("content")):
            if block.get("type") == "tool_result":
                event.tool_results.append(
                    ToolResultRecord(
                        tool_use_id=block.get("tool_use_id"),
                        result_bytes=_result_size_bytes(block.get("content")),
                        is_error=bool(block.get("is_error")),
                    )
                )
        side_record = raw.get("toolUseResult")
        if (
            isinstance(side_record, dict)
            and isinstance(side_record.get("agentId"), str)
            and event.tool_results
            and event.tool_results[0].tool_use_id
        ):
            event.agent_link = (
                event.tool_results[0].tool_use_id,
                side_record["agentId"],
            )
    else:  # system
        subtype = raw.get("subtype")
        if subtype == "compact_boundary":
            event.compact_boundary = True
            meta = raw.get("compactMetadata")
            if isinstance(meta, dict) and isinstance(meta.get("preTokens"), int):
                event.compact_pre_tokens = meta["preTokens"]
        elif subtype == "api_error":
            event.is_api_error = True
            if isinstance(raw.get("retryAttempt"), int):
                event.retry_attempt = raw["retryAttempt"]
    return event


def _iter_blocks(content: Any) -> Iterator[dict[str, Any]]:
    """Yield dict content blocks from a message content field, tolerating any shape."""
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict):
                yield block


def _tool_display_name(name: str, tool_input: Any) -> str:
    """Return the aggregation label for a tool_use block.

    Skill invocations break out per skill (Skill:commit-msg) and Agent
    dispatches per subagent type (Agent:Explore) — one lumped row would
    hide which custom skill or agent kind dominates the ranking. The
    discriminator comes from the tool input; absent or malformed input
    falls back to the plain tool name.
    """
    if isinstance(tool_input, dict):
        if name == "Skill":
            skill = tool_input.get("skill")
            if isinstance(skill, str) and skill:
                return f"Skill:{skill}"
        elif name in ("Agent", "Task"):
            subagent_type = tool_input.get("subagent_type")
            if isinstance(subagent_type, str) and subagent_type:
                return f"{name}:{subagent_type}"
    return name


def _extract_file_path(tool_input: Any) -> str | None:
    """Pull a file path out of a tool_use input dict when one exists."""
    if not isinstance(tool_input, dict):
        return None
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _normalize_usage(raw: Any) -> Usage | None:
    """Map a raw usage dict onto Usage via the alias layer.

    Returns None when raw is not a dict or carries no recognized token
    field, so callers can distinguish absent usage from zero usage.
    """
    if not isinstance(raw, dict):
        return None
    values: dict[str, int] = {}
    recognized = False
    for field_name, aliases in USAGE_ALIASES.items():
        value = 0
        for alias in aliases:
            candidate = raw.get(alias)
            if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
                value = int(candidate)
                recognized = True
                break
        values[field_name] = value
    return Usage(**values) if recognized else None


def _result_size_bytes(content: Any) -> int:
    """Measure the serialized size of a tool_result content payload.

    Strings count as their UTF-8 length; block lists count text blocks by
    text length and any other block by the length of its JSON
    serialization (images therefore count their base64 payload). The
    intent is a stable, comparable proxy for what re-enters the context.
    """
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.encode("utf-8", errors="replace"))
    if isinstance(content, list):
        total = 0
        for block in content:
            if (
                isinstance(block, dict)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
            ):
                total += len(block["text"].encode("utf-8", errors="replace"))
            else:
                total += _json_size(block)
        return total
    return _json_size(content)


def _json_size(value: Any) -> int:
    """Return the UTF-8 length of a value's JSON serialization, 0 on failure."""
    try:
        return len(json.dumps(value, ensure_ascii=False).encode("utf-8", errors="replace"))
    except (TypeError, ValueError):
        return 0


def _parse_timestamp(raw: Any) -> datetime | None:
    """Parse an ISO-8601 transcript timestamp, returning None on failure.

    Naive values are assumed UTC so all downstream comparisons stay
    timezone-aware.
    """
    if not isinstance(raw, str) or not raw:
        return None
    text = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed
