# Architecture

claudeye is a pragmatic-layered Python package. Dependencies flow one way toward
the domain; the CLI wires the pipeline together.

```
claudeye/
  __init__.py    __version__ + public re-exports
  __main__.py    python -m claudeye
  cli.py         argument parsing, run_analyze, main (wiring + user I/O)
  domain/        usage · events · stats · advice     (frozen value objects, read models)
  ingest/        source port · claude/ · codex/ · cache · settings  (source adapters)
  analyze/       aggregate · advice · summary         (pure aggregation)
  render/        template · html                      (summary dict -> artifacts)
```

```mermaid
flowchart LR
    CJSONL["~/.claude/projects<br>session · subagent JSONL"]
    XJSONL["~/.codex/sessions<br>rollout JSONL"]
    subgraph INGEST["ingest"]
        subgraph PORT["SessionSource port"]
            CLAUDE["ClaudeSource<br>lenient parser"]
            CODEX["CodexSource<br>lenient parser"]
        end
        CACHE["digest cache"]
    end
    subgraph ANALYZE["analyze"]
        AGG["analyze_events<br>global dedup"]
        SUM["build_summary<br>summary dict + advice"]
    end
    subgraph RENDER["render"]
        HTML["render_html"]
        RJSON["render_json"]
    end
    CLI["cli<br>--source · presets · mtime prefilter"]
    REPORT["report.html"]
    SUMJSON["summary.json"]

    CJSONL --> CLAUDE --> CACHE
    XJSONL --> CODEX --> CACHE
    CACHE -->|Event stream| AGG -->|AnalysisResult| SUM
    SUM --> HTML --> REPORT
    SUM --> RJSON --> SUMJSON
    CLI -.->|resolves source| PORT

    classDef external fill:#e8f4fd,stroke:#7ab8e8,color:#2c6e9e
    class CJSONL,XJSONL,REPORT,SUMJSON external
```

## Layers

- **domain** — pure, dependency-free. Frozen value objects (`Usage`,
  `AdviceConfig`) and mutable read-model accumulators (`SessionStats`,
  `SkillChainStats`, `AnalysisResult`). Nothing here imports the other layers.
- **ingest** — the only filesystem layer, organized as source adapters behind
  the `SessionSource` port (`name` / `detect` / `iter_session_files` / `parse`).
  `ingest/claude/` reads Claude Code project transcripts; `ingest/codex/` reads
  OpenAI Codex rollouts, collapsing its dual stream (`response_item` is
  canonical, `event_msg` is mined only for token counts) and reconstructing
  per-turn usage from Codex's periodic token events. Each adapter normalizes
  its format onto domain Events — stamping `Event.source` and a corpus-stable
  uuid — so everything downstream is agent-agnostic. Parsing is lenient (never
  raising per line — problems become `ParseWarning`s); the extraction digest
  cache and personal-config loading live here too.
- **analyze** — pure, no I/O. `analyze_events` folds the Event stream into read
  models; `build_summary` freezes them into the summary dict, running the advice
  rules along the way.
- **render** — consumes the summary dict only and produces the self-contained
  HTML and the JSON artifact.
- **cli** — parses arguments and orchestrates ingest → analyze → render, owning
  the only user-facing I/O (stdout, opening the browser).

## Two contracts

1. **Lenient parsing.** The parser never raises on a bad line; it collects a
   `ParseWarning` and moves on, and the warnings surface in the report so the
   reader can judge how much of the corpus the numbers cover.

2. **The summary dict.** `build_summary` returns one plain, JSON-serializable
   dict — the single boundary between analyze and render. Because the report
   embeds exactly this dict, the `--json` artifact and the report's data are
   always identical.

## Global dedup

Session fork/continue copies historical lines verbatim into the new session
file, uuid included (verified against real transcripts). `analyze_events` keeps
one global typed seen-set: `("line", uuid)` counts each physical line once;
`("msg", message_id)` deduplicates streamed usage; `("use"/"res", tool_use_id)`
guards repeated tool blocks. Without this, per-session counting inflated tokens
~8x and tool calls ~6x on the real corpus.

Identity is an adapter responsibility: Claude lines carry their own uuid, while
the Codex adapter synthesizes a corpus-stable one (`session id + line number`)
and dedups `sessions/` vs `archived_sessions/` copies at discovery — so the
seen-set logic above stays agent-agnostic.

## Digest cache

Second and later runs read a per-file **extraction** digest
(`~/.cache/claudeye/digests`, gzip JSONL, ~1% of the source). Only extraction is
cached, never aggregates — global fork dedup makes aggregates non-composable per
file, so `analyze_events` always re-runs over the cheap digested events. A digest
is keyed by `(mtime_ns, size, parser version, schema)`; any mismatch or defect
re-extracts silently. Measured effect: warm `--all` 15s → 3.4s.
