"""Render layer: the summary dict into self-contained artifacts."""

from __future__ import annotations

from claudeye.render.datadir import render_data_dir
from claudeye.render.html import render_html, render_json

__all__ = ["render_data_dir", "render_html", "render_json"]
