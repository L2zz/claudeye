"""ClaudeSource — the Claude Code adapter behind the SessionSource port.

A thin wrapper: discovery and parsing already live in this package's
parser module; ClaudeSource exposes them under the port's uniform shape so
the CLI and digest cache can treat every agent identically.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from claudeye.domain import Event, ParseWarning, SessionFile
from claudeye.ingest.claude.parser import iter_session_files, parse_transcript


class ClaudeSource:
    """SessionSource for Claude Code transcripts under ~/.claude/projects."""

    name = "claude"

    def detect(self, home: Path) -> Path | None:
        """Return ~/.claude/projects when it exists, else None."""
        root = home / ".claude" / "projects"
        return root if root.is_dir() else None

    def iter_session_files(
        self, root: Path, project_filter: str | None = None
    ) -> Iterator[SessionFile]:
        """Discover Claude Code transcripts under root."""
        return iter_session_files(root, project_filter)

    def parse(self, session_file: SessionFile, warnings: list[ParseWarning]) -> Iterator[Event]:
        """Parse one Claude Code transcript into Events."""
        return parse_transcript(session_file, warnings)
