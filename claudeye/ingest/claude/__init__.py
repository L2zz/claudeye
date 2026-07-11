"""Claude Code source adapter: discovery, lenient parsing, ClaudeSource.

Re-exports the parser helpers the wider package and test suite reference by
their historical names so moving them under this adapter stays transparent.
"""

from __future__ import annotations

from claudeye.ingest.claude.parser import (
    SYNTHETIC_MODEL,
    _tool_display_name,
    iter_session_files,
    parse_transcript,
)
from claudeye.ingest.claude.source import ClaudeSource

__all__ = [
    "SYNTHETIC_MODEL",
    "ClaudeSource",
    "_tool_display_name",
    "iter_session_files",
    "parse_transcript",
]
