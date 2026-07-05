"""Enable `python -m claudeye`."""

from __future__ import annotations

import sys

from claudeye.cli import main

if __name__ == "__main__":
    sys.exit(main())
