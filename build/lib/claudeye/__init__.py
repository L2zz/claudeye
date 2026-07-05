"""claudeye — an eye on your Claude Code usage.

Package layout (pragmatic layered, dependencies flow one way):
  domain  — pure value objects and read models
  ingest  — filesystem discovery, lenient JSONL parsing, digest cache
  analyze — pure aggregation into the summary dict
  render  — summary dict into HTML/JSON artifacts
  cli     — argument parsing and orchestration

This package root re-exports the public surface (and the handful of
internal helpers the test suite exercises) so `import claudeye` is the one
import callers and tests need.
"""

from __future__ import annotations

# Defined before the submodule imports below: ingest.cache and
# analyze.summary read claudeye.__version__ during their own import.
__version__ = "0.1.0"

from claudeye.analyze import (
    CONFIDENCE_NOTES,
    VERSION,
    _advice_level,
    _build_advice,
    advice_rule_catalog,
    analyze_events,
    build_summary,
)
from claudeye.cli import _resolve_since, build_arg_parser, main
from claudeye.domain import (
    ADVICE_BASE_LEVEL,
    LEVEL_ORDER,
    AdviceConfig,
    AnalysisResult,
    Event,
    ParseWarning,
    SessionFile,
    SessionStats,
    SkillChainStats,
    ToolResultRecord,
    ToolUseCall,
    Usage,
)
from claudeye.ingest import (
    SYNTHETIC_MODEL,
    _digest_dir,
    _parse_timestamp,
    _tool_display_name,
    iter_session_files,
    load_advice_config,
    load_or_parse_transcript,
    parse_transcript,
)
from claudeye.render import render_html, render_json

__all__ = [
    "ADVICE_BASE_LEVEL",
    "CONFIDENCE_NOTES",
    "LEVEL_ORDER",
    "SYNTHETIC_MODEL",
    "VERSION",
    "AdviceConfig",
    "AnalysisResult",
    "Event",
    "ParseWarning",
    "SessionFile",
    "SessionStats",
    "SkillChainStats",
    "ToolResultRecord",
    "ToolUseCall",
    "Usage",
    "__version__",
    "_advice_level",
    "_resolve_since",
    "_build_advice",
    "_digest_dir",
    "_parse_timestamp",
    "_tool_display_name",
    "advice_rule_catalog",
    "analyze_events",
    "build_arg_parser",
    "build_summary",
    "iter_session_files",
    "load_advice_config",
    "load_or_parse_transcript",
    "main",
    "parse_transcript",
    "render_html",
    "render_json",
]
