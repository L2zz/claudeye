"""Token usage value object.

Usage is the core value object of the analyzer: the four token counters
the API reports for one assistant message. It is a frozen value object —
immutable, compared by value — so accumulation returns a new Usage rather
than mutating in place. Accumulators rebind their field (usage += other).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Usage:
    """Token usage reported by the API for one assistant message.

    Cache read and cache creation are kept separate from plain input
    because their ratio is the main context-health signal downstream.
    Values are message-level facts (confidence: measured); they are never
    attributed to individual tools. Immutable: combine with ``+``.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        """Return a new Usage with the two records' counters summed."""
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_tokens + other.cache_read_tokens,
            self.cache_creation_tokens + other.cache_creation_tokens,
        )

    def total(self) -> int:
        """Return the sum of all four token counters."""
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_creation_tokens
        )
