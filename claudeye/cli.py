"""Command-line entry point: argument parsing and orchestration.

The CLI wires the layers together — ingest -> analyze -> render — and owns
the only user-facing I/O (stdout, the browser). `analyze` is the sole
subcommand and the default, so `claudeye --today` reads like a native tool.
"""

from __future__ import annotations

import argparse
import sys
import time
import webbrowser
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

from claudeye import __version__ as VERSION
from claudeye.analyze import analyze_events, build_summary
from claudeye.domain import AdviceConfig, Event, ParseWarning
from claudeye.ingest import (
    SOURCES,
    SessionSource,
    _digest_dir,
    load_advice_config,
    load_or_parse_transcript,
    resolve_source,
)
from claudeye.render import render_data_dir, render_html, render_json


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI: analyze --input --out [--json --redact-paths --since --project]."""
    parser = argparse.ArgumentParser(
        prog="claudeye",
        description="claudeye — an eye on your Claude Code usage: find context-waste "
        "patterns in local transcripts.",
    )
    parser.add_argument("--version", action="version", version=f"claudeye {VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser(
        "analyze",
        help="parse transcripts and write the HTML report",
        description="Parse JSONL transcripts, aggregate, and render the report.",
    )
    analyze.add_argument(
        "--source",
        default="claude",
        choices=[*sorted(SOURCES), "auto"],
        help="agent whose sessions to analyze: claude, codex, or auto "
        "(every agent whose default root exists); default: claude",
    )
    analyze.add_argument(
        "--input",
        default=None,
        help="session root to scan (default: the chosen source's own root — "
        "~/.claude/projects for claude, ~/.codex/sessions for codex); "
        "ignored with --source auto",
    )
    analyze.add_argument(
        "--out", default="report.html", help="HTML report path (default: report.html)"
    )
    analyze.add_argument(
        "--open",
        dest="open_report",
        action="store_true",
        help="open the HTML report in your browser when done",
    )
    analyze.add_argument(
        "--json",
        dest="json_out",
        default=None,
        metavar="PATH",
        help="also write the summary JSON artifact to PATH",
    )
    analyze.add_argument(
        "--data-dir",
        dest="data_dir",
        default=None,
        metavar="DIR",
        help="also write one file per facet into DIR (INDEX.md, <facet>.json, "
        "advice.txt) for agent consumption via cat",
    )
    analyze.add_argument(
        "--redact-paths",
        action="store_true",
        help="hash directories in reported paths, keep basenames",
    )
    analyze.add_argument(
        "--no-cache",
        action="store_true",
        help="bypass the per-file extraction digest cache (always reparse raw)",
    )
    config_group = analyze.add_mutually_exclusive_group()
    config_group.add_argument(
        "--config",
        default=None,
        metavar="PATH",
        help="advice-threshold overrides as JSON (default: "
        "~/.config/claudeye/config.json when present)",
    )
    config_group.add_argument(
        "--no-config",
        action="store_true",
        help="ignore the default config file; use built-in advice thresholds",
    )
    period = analyze.add_mutually_exclusive_group()
    period.add_argument(
        "--since",
        default=None,
        metavar="ISO",
        help="keep events at/after this local date or datetime (e.g. 2026-06-01)",
    )
    period.add_argument(
        "--today",
        action="store_true",
        help="only events since today's local midnight",
    )
    period.add_argument(
        "--one-week",
        dest="one_week",
        action="store_true",
        help="only events from the last 7 days (midnight-aligned)",
    )
    period.add_argument(
        "--one-month",
        dest="one_month",
        action="store_true",
        help="only events from the last 30 days (midnight-aligned)",
    )
    period.add_argument(
        "--all",
        action="store_true",
        help="no time filter (the default; kept for scriptable symmetry)",
    )
    analyze.add_argument(
        "--project",
        default=None,
        metavar="SUBSTR",
        help="only project directories whose name contains SUBSTR (case-insensitive)",
    )
    analyze.add_argument(
        "--lang",
        default="en",
        choices=["en", "ko"],
        help="report UI language (default: en; switchable in the report too)",
    )
    analyze.set_defaults(func=run_analyze)
    return parser


def _parse_since(text: str) -> datetime:
    """Parse the --since value; naive input is taken in local time.

    Raises:
      ValueError: when the text is not an ISO date or datetime.
    """
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed


def _resolve_since(args: argparse.Namespace, now: datetime | None = None) -> datetime | None:
    """Resolve --since and the period presets into one cutoff instant.

    Presets are midnight-aligned in local time so the daily chart keeps
    whole days: --today cuts at today's 00:00, --one-week 7 days and
    --one-month 30 days before that midnight. --all (or no flag) means
    no cutoff. argparse guarantees the flags are mutually exclusive.

    Args:
      args: Parsed analyze arguments.
      now: Injection point for tests; defaults to the current instant.

    Raises:
      ValueError: when --since text is not an ISO date or datetime.
    """
    if args.since:
        return _parse_since(args.since)
    midnight = (
        (now or datetime.now(timezone.utc))
        .astimezone()
        .replace(hour=0, minute=0, second=0, microsecond=0)
    )
    if getattr(args, "today", False):
        return midnight
    if getattr(args, "one_week", False):
        return midnight - timedelta(days=7)
    if getattr(args, "one_month", False):
        return midnight - timedelta(days=30)
    return None


def _mtime_before(path: Path, cutoff: datetime) -> bool:
    """Return True when the file's last write predates the cutoff.

    Used as a safe --since fast path: transcript lines are appended as
    they happen, so no line inside a file can carry a timestamp newer
    than the file's own mtime. Stat failures return False so the parser
    still gets a chance at the file.
    """
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return datetime.fromtimestamp(mtime, tz=timezone.utc) < cutoff


def _resolve_sources(args: argparse.Namespace) -> list[tuple[SessionSource, Path]]:
    """Resolve --source/--input into the (adapter, root) pairs to scan.

    'auto' includes every registered agent whose own default root exists
    under the home directory; a named source uses --input when given, else
    its detected default root.

    Raises:
      FileNotFoundError: when no usable session root can be resolved.
    """
    home = Path.home()
    source_name = getattr(args, "source", "claude")
    if source_name == "auto":
        pairs: list[tuple[SessionSource, Path]] = []
        for source in SOURCES.values():
            root = source.detect(home)
            if root is not None:
                pairs.append((source, root))
        if not pairs:
            raise FileNotFoundError(
                "no known agent sessions found (looked for the claude and codex roots)"
            )
        return pairs
    source = resolve_source(source_name)
    if args.input:
        root = Path(args.input).expanduser()
        if not root.is_dir():
            raise FileNotFoundError(f"input directory not found: {root}")
        return [(source, root)]
    detected = source.detect(home)
    if detected is None:
        raise FileNotFoundError(
            f"no {source.name} session root found under {home}; pass --input to point at one"
        )
    return [(source, detected)]


def run_analyze(args: argparse.Namespace) -> int:
    """Execute the analyze subcommand end to end, returning an exit code.

    Orchestrates ingest -> analyze -> render, writes the HTML report and
    optional JSON artifact, and prints a one-paragraph closing summary
    (sessions, warnings, top pollution source) to stdout.
    """
    started = time.monotonic()
    try:
        since = _resolve_since(args)
    except ValueError:
        print(
            f"error: --since must be ISO date/datetime, got: {args.since}",
            file=sys.stderr,
        )
        return 2
    try:
        source_roots = _resolve_sources(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if getattr(args, "no_config", False):
        advice_cfg, config_source = AdviceConfig(), None
    else:
        advice_cfg, config_source = load_advice_config(args.config)

    warnings: list[ParseWarning] = []
    cache_dir = None if getattr(args, "no_cache", False) else _digest_dir()

    def all_events() -> Iterator[Event]:
        for source, root in source_roots:
            for session_file in source.iter_session_files(root, args.project):
                if since is not None and _mtime_before(session_file.path, since):
                    continue  # a file cannot hold lines newer than its own mtime
                yield from load_or_parse_transcript(
                    session_file, warnings, cache_dir, source=source
                )

    result = analyze_events(all_events(), since=since)
    summary = build_summary(
        result,
        warnings,
        input_root=[str(root) for _, root in source_roots],
        since=since,
        project_filter=args.project,
        redact_paths=args.redact_paths,
        advice_config=advice_cfg,
        config_source=config_source,
        lang=getattr(args, "lang", "en"),
    )

    out_path = Path(args.out)
    out_path.write_text(render_html(summary), encoding="utf-8")
    written = [str(out_path)]
    if args.json_out:
        json_path = Path(args.json_out)
        json_path.write_text(render_json(summary), encoding="utf-8")
        written.append(str(json_path))
    if getattr(args, "data_dir", None):
        facet_paths = render_data_dir(summary, Path(args.data_dir))
        written.append(f"{args.data_dir}/ ({len(facet_paths)} facet files)")

    elapsed = time.monotonic() - started
    totals = summary["totals"]
    top_tool = summary["by_tool"][0]["name"] if summary["by_tool"] else "n/a"
    print(
        f"analyzed {totals['sessions']} sessions across {totals['projects']} projects "
        f"in {elapsed:.1f}s — {totals['total_tokens']:,} tokens, "
        f"top pollution source: {top_tool}, "
        f"wasted re-reads: {totals['wasted_reads']}, "
        f"parse warnings: {len(warnings)}"
    )
    print("wrote: " + ", ".join(written))
    if getattr(args, "open_report", False):
        webbrowser.open(out_path.resolve().as_uri())
    if elapsed > 5:
        print(
            "note: cold run exceeded 5s — the PROPOSAL roadmap trigger for a DuckDB store; "
            "narrow with --since/--project meanwhile",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    `analyze` is the sole subcommand and the default: `claudeye --today`
    is treated as `claudeye analyze --today` so the packaged command
    reads like a native tool. Explicit `analyze`, `-h/--help`, and
    `--version` pass through untouched.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    passthrough = {"analyze", "-h", "--help", "--version"}
    if not argv or argv[0] not in passthrough:
        argv = ["analyze"] + argv
    args = build_arg_parser().parse_args(argv)
    return args.func(args)
