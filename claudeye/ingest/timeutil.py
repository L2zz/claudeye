"""Timestamp parsing shared across source adapters and the digest cache.

Kept source-agnostic: both the Claude adapter (parsing raw lines) and the
digest cache (decoding stored ISO strings) need the same lenient ISO-8601
handling, so it lives here rather than inside any one adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


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
