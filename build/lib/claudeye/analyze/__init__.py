"""Analyze layer: pure aggregation and summary building.

Depends on domain (value objects) and ingest (SYNTHETIC_MODEL). Produces
the summary dict — the single contract consumed by the render layer.
"""

from __future__ import annotations

from claudeye.analyze.advice import (
    _advice_level,
    _build_advice,
    advice_rule_catalog,
)
from claudeye.analyze.aggregate import _fold_assistant, analyze_events
from claudeye.analyze.summary import (
    CONFIDENCE_NOTES,
    VERSION,
    build_summary,
)

__all__ = [
    "CONFIDENCE_NOTES",
    "VERSION",
    "_advice_level",
    "_build_advice",
    "_fold_assistant",
    "advice_rule_catalog",
    "analyze_events",
    "build_summary",
]
