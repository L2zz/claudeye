# Concept

claudeye is a local, closed-loop analyzer of coding-agent transcripts — Claude
Code (`~/.claude/projects`) and OpenAI Codex (`~/.codex/sessions`), selected with
`--source`. Each agent has a lenient adapter behind one `SessionSource` port that
normalizes its on-disk format onto a shared Event model; the rest of the pipeline
is agent-agnostic. It finds context-waste patterns and emits a self-contained
HTML report plus a summary JSON. This document is the source of truth for *why*
it exists and *what lines it will not cross*.

## Why it exists

Two motivations, in order:

1. **Observe your own harness.** Over time, sessions, skills, and subagents pile
   up and it becomes hard to feel where tokens leak, which files get re-read,
   which skills are heavy. claudeye turns the raw transcript history into one
   page that answers "what is polluting my context?". It is **not** a billing
   tool (use ccusage for cost) — it is a *waste-pattern detector*.

2. **Evolve the harness with an agent.** The real goal is a loop: an agent reads
   the observation and improves the harness (skills, rules, CLAUDE.md). So the
   output is deliberately **static, self-contained, and easy for an agent to
   parse** — an HTML page for humans, a summary JSON for agents, and an advice
   section that has already translated waste into actionable, levelled hints.
   The author consumes this from a weekly `dream` routine.

## What it is / is not

- **Closed loop, offline.** Every run re-parses local JSONL. Nothing is sent
  anywhere; the report makes no network requests (no CDN, fonts, or scripts).
- **Zero runtime dependency.** Standard library only. Dev tooling (ruff, mypy,
  pytest) is separate and never ships to users.
- **No raw transcript text.** Prompts, tool outputs, and file contents never
  enter the summary or the report — only aggregated numbers. Paths are
  home-relativized and can be hashed with `--redact-paths`.
- **Not a billing source.** No cost estimation at all — the report tracks
  context waste, not spend. Use ccusage for cost.

## Confidence discipline

Measured and estimated values are never blended. Every metric family carries a
label, echoed in the report's "Confidence notes":

- **measured** — read directly from transcript facts (tokens deduplicated by
  line uuid and API message id; tool calls by tool_use_id; tool result bytes;
  cache efficiency; subagent-type attribution via `toolUseResult.agentId`).
- **inferred** — joined or derived with an assumption (duplicate-read detection
  via `Read` file_path repeats only; fork attribution; advice remedies).
- **approximate by design** — known-lossy (per-tool token attribution is *not*
  done — usage is per API response, so splitting it per tool would be a guess).

## Invariants (enforced in review)

These are the lines the codebase holds; the `.coderabbit.yaml` review config
encodes them so a PR that crosses them is flagged:

- **Layer boundary.** Dependencies flow one way: `ingest -> analyze -> render`,
  with `cli` wiring them. The summary dict from `build_summary` is the *only*
  contract between analyze and render.
- **Self-contained report.** No external requests; every dynamic value reaches
  the DOM via `textContent` (never `innerHTML`), so hostile strings in paths or
  names cannot inject markup.
- **Global dedup.** Fork/continue copies historical lines verbatim (uuid
  included). Counting deduplicates corpus-wide, or per-session counting inflates
  tokens ~8x and tool calls ~6x (measured).
- **Advice single source.** Advice rules run in Python; the report derives all
  warning colors and flags from advice targets. No threshold logic is duplicated
  in the report JS.
- **Attribution vs container.** Containers (session, project) rank by total
  tokens — cache_read is their real footprint. Attribution slices (skill, agent)
  rank by *new tokens* (input + output + cache write); cache_read there is
  ambient and double-counted across slices, so it would mis-rank them.

The negotiation records that produced this scope live in
[history/](history/) (codex-debate convergence logs).
