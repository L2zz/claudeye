"""Summary dict -> self-contained artifacts (HTML and JSON).

The render layer consumes the summary dict — the single contract with
analyze — and produces output. It reaches into no other layer. Raw
transcript text never appears here because it never entered the summary.
"""

from __future__ import annotations

import json
from typing import Any

from claudeye.render.template import _HTML_TEMPLATE


def render_html(summary: dict[str, Any]) -> str:
    """Render the summary into one dependency-free HTML document.

    The document embeds the summary as a JSON script tag and draws the
    four fixed views with inline vanilla JS/SVG (no CDN, works offline):
    tool pollution ranking bars, daily token stacked bars, sortable
    session table with cache-efficiency and waste flags, and the
    top duplicate-read files list. Raw transcript text is never present.
    All dynamic values reach the DOM through textContent, so hostile
    strings in paths or model names cannot inject markup.
    """
    payload = json.dumps(summary, ensure_ascii=False).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("__SUMMARY_JSON__", payload)


def render_json(summary: dict[str, Any]) -> str:
    """Serialize the summary dict deterministically for the --json artifact."""
    return json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
