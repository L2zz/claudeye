"""Normalized transcript records.

The lenient parser (ingest layer) maps heterogeneous raw JSONL lines onto
these records; the analyze layer consumes them and never sees raw JSON.
They are data-transfer records, nullable wherever the raw schema has
proven optional — downstream code must tolerate None.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from claudeye.domain.usage import Usage


@dataclass
class ParseWarning:
    """One transcript line the parser could not fully understand.

    Collected instead of raised so a single corrupt line never discards
    a whole session file. Surfaced in the summary so the user can judge
    how much of the corpus the numbers actually cover.
    """

    file: str
    line_no: int
    reason: str


@dataclass
class SessionFile:
    """One transcript file on disk and the session it belongs to.

    Produced by discovery, consumed by the parser. A session usually has
    one main transcript at project-dir/session-id.jsonl; sessions that
    spawned subagents additionally have per-agent transcripts under
    project-dir/session-id/subagents/agent-*.jsonl, which carry the same
    session id and are merged into the parent session downstream.
    """

    project: str
    session_id: str
    path: Path
    agent_id: str | None = None


@dataclass
class ToolUseCall:
    """One tool invocation requested by an assistant message.

    The id is the join key toward the matching ToolResultRecord and is
    nullable: a missing id downgrades size attribution for that call, it
    never drops the call count. file_path is pre-extracted from the tool
    input for read-like tools so the duplicate-read heuristic does not
    need to keep raw inputs around.
    """

    tool_use_id: str | None
    name: str
    file_path: str | None = None
    subagent_type: str | None = None


@dataclass
class ToolResultRecord:
    """Size and error facts about one tool result returned to the model.

    result_bytes measures the serialized text that re-enters the context
    window (confidence: measured) — the pollution metric this tool exists
    for. It is not the on-disk size of toolUseResult side records.
    """

    tool_use_id: str | None
    result_bytes: int
    is_error: bool = False


@dataclass
class Event:
    """One normalized transcript line that matters to the analyzer.

    The lenient parser maps heterogeneous raw lines (assistant / user /
    system, main or subagent) onto this single shape; analyze consumes
    Events only and never sees raw JSON. Fields are nullable wherever the
    raw schema has proven optional — downstream code must tolerate None.

    Attributes:
      project: Project slug directory name the session lives under.
      session_id: Session UUID shared by main and subagent transcripts.
      kind: Raw line type, one of assistant, user or system.
      timestamp: Line timestamp, None when absent or unparseable.
      uuid: Line uuid. Fork/continue copies a line verbatim into the new
        session file, uuid included, so this is the corpus-wide identity
        used to count each line once (verified against real transcripts).
      agent_id: Subagent id when the line comes from a sidechain
        transcript, None for the main conversation.
      message_id: API message id used to deduplicate usage across
        multiple JSONL lines of the same streamed assistant message.
      attribution_skill: Skill name the harness stamped on this assistant
        turn (attributionSkill) — the measured basis for per-skill chain
        accounting; None for turns outside any skill context.
      model: Model name on assistant lines.
      usage: Token usage on assistant lines.
      request_id: API request id on assistant lines.
      tool_uses: Tool invocations contained in this line.
      tool_results: Tool results contained in this line.
      agent_link: (tool_use_id, agent_id) pair when this user line's
        toolUseResult carries an agentId — the measured join between an
        Agent dispatch and its sidechain transcript.
      is_api_error: True for synthesized error placeholders and system
        api_error lines.
      retry_attempt: Retry ordinal on system retry lines.
      compact_boundary: True on system lines marking a compaction.
      compact_pre_tokens: Context size before compaction when recorded.
      is_compact_summary: True on the user line carrying the compact
        summary text.
    """

    project: str
    session_id: str
    kind: str
    timestamp: datetime | None
    uuid: str | None = None
    agent_id: str | None = None
    message_id: str | None = None
    attribution_skill: str | None = None
    model: str | None = None
    usage: Usage | None = None
    request_id: str | None = None
    tool_uses: list[ToolUseCall] = field(default_factory=list)
    tool_results: list[ToolResultRecord] = field(default_factory=list)
    agent_link: tuple[str, str] | None = None
    is_api_error: bool = False
    retry_attempt: int | None = None
    compact_boundary: bool = False
    compact_pre_tokens: int | None = None
    is_compact_summary: bool = False
