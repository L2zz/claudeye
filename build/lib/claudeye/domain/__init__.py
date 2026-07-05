"""Domain layer: pure, dependency-free value objects and read models.

Nothing here imports from ingest, analyze, or render — dependencies flow
one way toward this layer. These are the shapes the rest of the pipeline
speaks in.
"""

from __future__ import annotations

from claudeye.domain.advice import (
    ADVICE_BASE_LEVEL,
    LEVEL_ORDER,
    AdviceConfig,
)
from claudeye.domain.events import (
    Event,
    ParseWarning,
    SessionFile,
    ToolResultRecord,
    ToolUseCall,
)
from claudeye.domain.stats import (
    WASTE_CACHE_EFF_MAX,
    WASTE_CACHE_MIN_REQUESTS,
    WASTE_DUP_READ_MIN,
    WASTE_ERRORS_MIN,
    AnalysisResult,
    SessionStats,
    SkillChainStats,
)
from claudeye.domain.usage import Usage

__all__ = [
    "ADVICE_BASE_LEVEL",
    "LEVEL_ORDER",
    "WASTE_CACHE_EFF_MAX",
    "WASTE_CACHE_MIN_REQUESTS",
    "WASTE_DUP_READ_MIN",
    "WASTE_ERRORS_MIN",
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
]
