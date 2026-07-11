"""CodexSource — the OpenAI Codex adapter behind the SessionSource port.

Wraps this package's discovery and parser under the port's uniform shape so
the CLI and digest cache drive Codex exactly like Claude Code.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from claudeye.domain import Event, ParseWarning, SessionFile
from claudeye.ingest.codex.parser import iter_session_files, parse_transcript


class CodexSource:
    """SessionSource for OpenAI Codex rollouts under ~/.codex/sessions."""

    name = "codex"

    def detect(self, home: Path) -> Path | None:
        """Return ~/.codex/sessions when it exists, else None."""
        root = home / ".codex" / "sessions"
        return root if root.is_dir() else None

    def iter_session_files(
        self, root: Path, project_filter: str | None = None
    ) -> Iterator[SessionFile]:
        """Discover Codex rollout transcripts under root."""
        return iter_session_files(root, project_filter)

    def parse(self, session_file: SessionFile, warnings: list[ParseWarning]) -> Iterator[Event]:
        """Parse one Codex rollout into Events."""
        return parse_transcript(session_file, warnings)
