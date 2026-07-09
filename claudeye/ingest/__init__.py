"""Ingest layer: source adapters, digest cache, config loading.

Depends only on the domain layer (plus the package version for cache
validity). A SessionSource adapter turns one agent's transcripts into a
stream of domain Events; the digest cache and the CLI drive any adapter
uniformly through the registry below.
"""

from __future__ import annotations

from claudeye.ingest.cache import _digest_dir, load_or_parse_transcript
from claudeye.ingest.claude import (
    SYNTHETIC_MODEL,
    ClaudeSource,
    _tool_display_name,
    iter_session_files,
    parse_transcript,
)
from claudeye.ingest.settings import load_advice_config
from claudeye.ingest.source import SessionSource
from claudeye.ingest.timeutil import _parse_timestamp

#: Registered source adapters keyed by their agent tag.
_CLAUDE = ClaudeSource()
SOURCES: dict[str, SessionSource] = {_CLAUDE.name: _CLAUDE}


def resolve_source(name: str) -> SessionSource:
    """Return the registered SessionSource for name.

    Raises:
      ValueError: when no adapter is registered under name.
    """
    try:
        return SOURCES[name]
    except KeyError:
        raise ValueError(f"unknown source: {name!r}") from None


__all__ = [
    "SOURCES",
    "SYNTHETIC_MODEL",
    "ClaudeSource",
    "SessionSource",
    "_digest_dir",
    "_parse_timestamp",
    "_tool_display_name",
    "iter_session_files",
    "load_advice_config",
    "load_or_parse_transcript",
    "parse_transcript",
    "resolve_source",
]
