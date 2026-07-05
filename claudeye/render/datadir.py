"""Summary dict -> a directory of per-facet files for agent consumption.

The HTML report is for humans; this output is for an agent (e.g. a `dream`
skill) that wants to `cat` exactly one facet without parsing the whole
summary. Every top-level summary key becomes DIR/<key>.json, plus two
convenience files: advice.txt (the advice list as plain lines, no JSON
parse needed) and INDEX.md (what each file holds and the headline
numbers, so a single `cat INDEX.md` orients the reader). Deterministic
and self-contained; raw transcript text never enters the summary, so it
cannot appear here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

#: One-line description per known facet, shown in INDEX.md. Unknown keys
#: (future facets) still get a file and an INDEX row with a generic note.
_FACET_DESCRIPTIONS = {
    "meta": "run metadata: tool version, input root, filters, confidence notes",
    "totals": "corpus-wide totals: sessions, projects, tokens, tool calls, wasted reads",
    "by_tool": "per-tool context pollution ranking (result bytes, calls, errors)",
    "by_day": "daily token matrix, split by model",
    "by_project": "per-project rollup (tokens, requests, subagent share)",
    "by_agent_type": "tokens attributed to each subagent type",
    "by_skill_chain": "per-skill tool chains (new tokens/turn, fan-out, composition)",
    "advice": "rule-based advice items with level, message, evidence",
    "advice_rules": "the full advice rule catalog and current definitions",
    "advice_thresholds": "the advice thresholds in effect (built-in or from config)",
    "sessions": "per-session stats (tokens, cache efficiency, compactions, waste flags)",
    "dup_reads": "files re-read across sessions (duplicate-read hotspots)",
    "parse_warnings": "lenient-parser warnings (line-level, sensitive text excluded)",
}


def _advice_lines(advice: list[dict[str, Any]]) -> str:
    """Render the advice list as plain text lines (no JSON parse needed)."""
    if not advice:
        return "no advice — nothing crossed the configured thresholds\n"
    lines = []
    for item in advice:
        level = str(item.get("level", "info")).upper()
        rule = item.get("rule", "?")
        message = item.get("message", "")
        confidence = item.get("confidence", "")
        lines.append(f"[{level}] {rule} — {message}")
        if confidence:
            lines.append(f"        confidence: {confidence}")
    return "\n".join(lines) + "\n"


def _index_markdown(summary: dict[str, Any], files: list[str]) -> str:
    """Build INDEX.md: headline numbers plus a row per emitted file."""
    meta = summary.get("meta", {})
    totals = summary.get("totals", {})
    lines = [
        "# claudeye data facets",
        "",
        f"- tool: {meta.get('tool', 'claudeye')} {meta.get('version', '')}".rstrip(),
        f"- generated: {meta.get('generated_at', '')}",
        f"- input root: {meta.get('input_root', '')}",
        f"- since: {meta.get('since') or 'all time'}",
        "",
        "## headline",
        "",
        f"- sessions: {totals.get('sessions', 0)}",
        f"- projects: {totals.get('projects', 0)}",
        f"- total tokens: {totals.get('total_tokens', 0):,}",
        f"- tool calls: {totals.get('tool_calls', 0):,}",
        f"- wasted re-reads: {totals.get('wasted_reads', 0)}",
        f"- parse warnings: {meta.get('parse_warnings_total', 0)}",
        "",
        "## files",
        "",
        "`cat` any file below to read just that facet.",
        "",
    ]
    for name in files:
        key = name[:-5] if name.endswith(".json") else name
        if name == "advice.txt":
            desc = "advice as plain text lines (same items as advice.json)"
        else:
            desc = _FACET_DESCRIPTIONS.get(key, "summary facet")
        lines.append(f"- `{name}` — {desc}")
    return "\n".join(lines) + "\n"


def render_data_dir(summary: dict[str, Any], out_dir: Path) -> list[Path]:
    """Write one file per summary facet into out_dir; return written paths.

    Emits DIR/<key>.json for every top-level summary key (so a new facet
    is exported automatically), plus advice.txt and INDEX.md. Overwrites
    existing facet files in place. Returns the paths written, INDEX.md last.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    names: list[str] = []

    for key, value in summary.items():
        path = out_dir / f"{key}.json"
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
        names.append(path.name)

    advice_txt = out_dir / "advice.txt"
    advice_txt.write_text(_advice_lines(summary.get("advice", [])), encoding="utf-8")
    written.append(advice_txt)
    names.append(advice_txt.name)

    index = out_dir / "INDEX.md"
    index.write_text(_index_markdown(summary, names), encoding="utf-8")
    written.append(index)
    return written
