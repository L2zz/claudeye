"""Ingest layer: discovery, lenient parsing, digest cache, config loading.

Depends only on the domain layer (plus the package version for cache
validity). Turns a projects directory into a stream of domain Events.
"""

from __future__ import annotations

from claudeye.ingest.cache import _digest_dir, load_or_parse_transcript
from claudeye.ingest.parser import (
    SYNTHETIC_MODEL,
    _parse_timestamp,
    _tool_display_name,
    iter_session_files,
    parse_transcript,
)
from claudeye.ingest.settings import load_advice_config

__all__ = [
    "SYNTHETIC_MODEL",
    "_digest_dir",
    "_parse_timestamp",
    "_tool_display_name",
    "iter_session_files",
    "load_advice_config",
    "load_or_parse_transcript",
    "parse_transcript",
]
