"""SessionSource port — the seam every agent adapter implements.

One coding agent (Claude Code, Codex, ...) stores its sessions in its own
on-disk format. A SessionSource is the anti-corruption boundary for one
such format: it discovers that agent's transcript files and normalizes
their lines into domain Events. The rest of the pipeline (digest cache,
analyze, render) speaks only Events and never learns which agent produced
them — adding an agent costs one adapter, not a pipeline fork.

The adapter also owns identity: it must stamp each Event with a
corpus-stable uuid so the core "count each uuid once" dedup stays
agent-agnostic.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

from claudeye.domain import Event, ParseWarning, SessionFile


class SessionSource(Protocol):
    """One agent's session format, normalized to Events.

    Structural (Protocol) rather than inherited so an adapter is any
    object that supplies these four members; concrete adapters live under
    ``ingest/<agent>/``.

    Attributes:
      name: Stable agent tag stamped onto every Event ("claude", "codex").
    """

    name: str

    def detect(self, home: Path) -> Path | None:
        """Return this agent's default root under home, or None if absent.

        Lets ``--source auto`` merge whichever agents are present without
        the caller hardcoding paths.
        """
        ...

    def iter_session_files(
        self, root: Path, project_filter: str | None = None
    ) -> Iterator[SessionFile]:
        """Discover transcript files under root.

        Discovery must not parse transcripts, but MAY peek a bounded
        amount of per-file metadata (a few leading lines) when the format
        keeps session identity inside the file — e.g. Codex carries its
        cwd in session_meta, and SessionFile.project must be fixed here
        for the digest cache to round-trip it. Claude needs no peek (the
        project is the directory name).
        """
        ...

    def parse(self, session_file: SessionFile, warnings: list[ParseWarning]) -> Iterator[Event]:
        """Parse one transcript into Events, appending problems to warnings."""
        ...
