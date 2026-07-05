"""Per-file extraction digest cache (codex-debate v0.3 (1)).

The cache stores EXTRACTION results only, never aggregates: global fork
dedup makes aggregates non-composable per file, so analyze always re-runs
over the (cheap) digested events. One gzip JSONL per source file: line 1
is a meta record carrying the validity key (mtime_ns, size, parser
version, digest schema); following lines are compact event records; parse
warnings ride along as "w" records so a cache hit reproduces them
faithfully. Any read or validation problem falls back to raw parsing
silently — the cache is best-effort and never a correctness dependency.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from claudeye import __version__ as VERSION
from claudeye.domain import (
    Event,
    ParseWarning,
    SessionFile,
    ToolResultRecord,
    ToolUseCall,
    Usage,
)
from claudeye.ingest.parser import _parse_timestamp, parse_transcript

#: Digest layout version, bumped when the record encoding changes.
DIGEST_SCHEMA = 4


def _digest_dir() -> Path:
    """Return the digest cache directory, honoring XDG_CACHE_HOME."""
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "claudeye" / "digests"


def _digest_path(source: Path, cache_dir: Path) -> Path:
    """Map a transcript path to its digest file path."""
    digest = hashlib.sha1(str(source).encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.jsonl.gz"


def _event_to_record(event: Event) -> dict[str, Any]:
    """Encode an Event as a compact digest record (None/empty omitted).

    Short keys keep digests small and fast to parse: k kind, t timestamp,
    u uuid, cwd cwd, ag agent_id, m message_id, as attribution skill,
    md model, us usage 4-tuple, ae api error, ra retry attempt, cb compact
    boundary, cp compact preTokens, tu tool_uses, tr tool_results, al agent link.
    """
    record: dict[str, Any] = {"k": event.kind}
    if event.timestamp is not None:
        record["t"] = event.timestamp.isoformat()
    if event.uuid is not None:
        record["u"] = event.uuid
    if event.cwd is not None:
        record["cwd"] = event.cwd
    if event.agent_id is not None:
        record["ag"] = event.agent_id
    if event.message_id is not None:
        record["m"] = event.message_id
    if event.attribution_skill is not None:
        record["as"] = event.attribution_skill
    if event.model is not None:
        record["md"] = event.model
    if event.usage is not None:
        usage = event.usage
        record["us"] = [
            usage.input_tokens,
            usage.output_tokens,
            usage.cache_read_tokens,
            usage.cache_creation_tokens,
        ]
    if event.is_api_error:
        record["ae"] = 1
    if event.retry_attempt is not None:
        record["ra"] = event.retry_attempt
    if event.compact_boundary:
        record["cb"] = 1
    if event.compact_pre_tokens is not None:
        record["cp"] = event.compact_pre_tokens
    if event.tool_uses:
        record["tu"] = [
            [call.tool_use_id, call.name, call.file_path, call.subagent_type]
            for call in event.tool_uses
        ]
    if event.tool_results:
        record["tr"] = [
            [res.tool_use_id, res.result_bytes, 1 if res.is_error else 0]
            for res in event.tool_results
        ]
    if event.agent_link is not None:
        record["al"] = list(event.agent_link)
    return record


def _record_to_event(record: dict[str, Any], session_file: SessionFile) -> Event:
    """Decode one digest record back into an Event (inverse of the encoder)."""
    usage = None
    if "us" in record:
        i, o, cr, cc = record["us"]
        usage = Usage(
            input_tokens=i,
            output_tokens=o,
            cache_read_tokens=cr,
            cache_creation_tokens=cc,
        )
    return Event(
        project=session_file.project,
        session_id=session_file.session_id,
        kind=record["k"],
        timestamp=_parse_timestamp(record.get("t")),
        uuid=record.get("u"),
        cwd=record.get("cwd"),
        # Prefer the stored agent_id: a main-transcript line can carry a raw
        # agentId that session_file.agent_id (subagent-file only) would miss,
        # so warm must reproduce what the parser captured (cold == warm).
        agent_id=record.get("ag") or session_file.agent_id,
        message_id=record.get("m"),
        attribution_skill=record.get("as"),
        model=record.get("md"),
        usage=usage,
        tool_uses=[
            ToolUseCall(tool_use_id=tid, name=name, file_path=path, subagent_type=stype)
            for tid, name, path, stype in record.get("tu", [])
        ],
        tool_results=[
            ToolResultRecord(tool_use_id=tid, result_bytes=size, is_error=bool(err))
            for tid, size, err in record.get("tr", [])
        ],
        agent_link=tuple(record["al"]) if "al" in record else None,
        is_api_error=bool(record.get("ae")),
        retry_attempt=record.get("ra"),
        compact_boundary=bool(record.get("cb")),
        compact_pre_tokens=record.get("cp"),
    )


def _read_digest(
    digest_file: Path,
    session_file: SessionFile,
    stat: os.stat_result,
    warnings: list[ParseWarning],
) -> list[Event] | None:
    """Load events from a digest when its validity key still matches.

    Returns None on any mismatch or defect (stale mtime/size, other
    parser VERSION, other schema, truncated or corrupt records) so the
    caller re-extracts from the raw transcript.
    """
    try:
        with gzip.open(digest_file, "rt", encoding="utf-8") as handle:
            meta = json.loads(handle.readline())
            if (
                meta.get("schema") != DIGEST_SCHEMA
                or meta.get("version") != VERSION
                or meta.get("mtime_ns") != stat.st_mtime_ns
                or meta.get("size") != stat.st_size
                or meta.get("complete") is not True
            ):
                return None
            events: list[Event] = []
            for line in handle:
                record = json.loads(line)
                if "w" in record:
                    for file_label, line_no, reason in record["w"]:
                        warnings.append(ParseWarning(file_label, line_no, reason))
                else:
                    events.append(_record_to_event(record, session_file))
            return events
    except (OSError, ValueError, KeyError, TypeError, EOFError):
        return None


def load_or_parse_transcript(
    session_file: SessionFile,
    warnings: list[ParseWarning],
    cache_dir: Path | None = None,
) -> Iterator[Event]:
    """Yield a transcript's Events through the digest cache.

    Cache hit streams decoded events; miss parses raw and rewrites the
    digest atomically (tmp file + os.replace) so a crashed or abandoned
    run never leaves a half-written digest in place. cache_dir=None
    disables caching entirely (--no-cache).
    """
    if cache_dir is None:
        yield from parse_transcript(session_file, warnings)
        return
    try:
        stat = session_file.path.stat()
    except OSError:
        yield from parse_transcript(session_file, warnings)
        return

    digest_file = _digest_path(session_file.path, cache_dir)
    cached = _read_digest(digest_file, session_file, stat, warnings)
    if cached is not None:
        yield from cached
        return

    local_warnings: list[ParseWarning] = []
    events = list(parse_transcript(session_file, local_warnings))
    warnings.extend(local_warnings)
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp_file = digest_file.with_suffix(".tmp")
        with gzip.open(tmp_file, "wt", encoding="utf-8", compresslevel=1) as handle:
            meta = {
                "schema": DIGEST_SCHEMA,
                "version": VERSION,
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "complete": True,
            }
            handle.write(json.dumps(meta) + "\n")
            for event in events:
                handle.write(json.dumps(_event_to_record(event), ensure_ascii=False) + "\n")
            if local_warnings:
                handle.write(
                    json.dumps({"w": [[w.file, w.line_no, w.reason] for w in local_warnings]})
                    + "\n"
                )
        os.replace(tmp_file, digest_file)
    except OSError:
        pass  # best-effort cache; the parse result is still served below
    yield from events
