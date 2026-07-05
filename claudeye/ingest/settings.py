"""Personal config loading (advice thresholds).

Reads a user's JSON config so tuned advice thresholds persist across
runs. A missing, unreadable, or invalid file degrades to defaults so a
broken config never blocks a run.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from claudeye.domain import AdviceConfig


def _config_path() -> Path:
    """Return the default config path, honoring XDG_CONFIG_HOME."""
    base = os.environ.get("XDG_CONFIG_HOME")
    root = Path(base) if base else Path.home() / ".config"
    return root / "claudeye" / "config.json"


def load_advice_config(
    explicit: str | None = None,
) -> tuple[AdviceConfig, str | None]:
    """Load advice thresholds from JSON, returning (config, source).

    Reads --config PATH when given, else the default config path when it
    exists. Missing, unreadable, or invalid files degrade to defaults
    with source None so a broken config never blocks a run.
    """
    path = Path(explicit).expanduser() if explicit else _config_path()
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError):
        return AdviceConfig(), None
    return AdviceConfig.from_dict(data), str(path)
