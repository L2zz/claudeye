# claudeye

**English** · [한국어](README.ko.md)

Look deep into Claude Code with claudeye. It reads Claude Code and Codex session
records and shows, in a single report, where your context is being wasted. It
runs locally as a static script and never sends your personal data out.

For self-improving harness setups, claudeye is the measurement layer: it turns
transcripts into measured, agent-readable facts your reflection loop can act on.

**Contents**

1. [Background](#1-background)
2. [Install](#2-install)
3. [Quick start](#3-quick-start)
4. [Report](#4-report)
5. [Agent facet files (`--data-dir`)](#5-agent-facet-files---data-dir)
6. [Personal config](#6-personal-config)
7. [Metric](#7-metric)
8. [Docs](#8-docs)
9. [Development · contributing](#9-development--contributing)
10. [License](#10-license)

## 1. Background

claudeye began as a way to observe a Claude Code harness and to turn that
observation into a data source for improving the harness.

### Harness monitoring

As sessions, skills, and subagents pile up, it gets hard to feel where tokens
leak, which files get re-read, and which skills are heavy. claudeye shows what is
polluting your context on a single page.

### The measurement half of a self-improving loop

claudeye's output is agent-readable, so it can feed the harness's own evolution
as an instrument → reflection → edit loop: claudeye measures, a reflection
routine reads the `--data-dir` facets, and the edits land in skills, rules, and
CLAUDE.md. Correction-capture tools record what you corrected in dialogue — the
qualitative half; claudeye measures what the transcripts actually show — the
quantitative half of the same loop. (This is the loop
[harness engineering](https://lilianweng.github.io/posts/2026-07-04-harness/)
asks for: measurable, objective metrics, with the file system as memory.)

For example, a weekly reflection skill reads the `--data-dir` output and turns
recurring waste into rule and skill improvements:

```md
---
name: weekly-harness-evolve
description: Read last week's claudeye output and propose harness improvements
---

1. `claudeye --one-week --data-dir /tmp/claudeye` — analyze the past week.
2. `cat /tmp/claudeye/advice.txt` — read the waste advice.
3. Turn recurring waste patterns into CLAUDE.md / skill-rule improvements.
```

> See [docs/concept.md](docs/concept.md) for the full background.

## 2. Install

- Only dependency: Python 3.9+

Pick whichever of the three is easiest.

Homebrew:

```bash
brew install L2zz/tap/claudeye
```

curl install script (uses uv / pipx / pip, whichever you have):

```bash
curl -fsSL https://raw.githubusercontent.com/L2zz/claudeye/main/install.sh | bash
```

uv / pipx / pip directly:

```bash
uv tool install git+https://github.com/L2zz/claudeye
# or
pipx install git+https://github.com/L2zz/claudeye
```

## 3. Quick start

`claudeye` analyzes your whole usage history (default: all) and writes
`report.html` in the current folder. Narrow the period and output with options:

```bash
claudeye                          # all time → report.html
claudeye --today --open           # today's report, opened right away
claudeye --one-week --project myproject  # last 7 days, one project only
claudeye --json summary.json      # also write the summary JSON
claudeye --data-dir facets/       # also write the agent facet files
```

| Option | Meaning |
|---|---|
| `--source` | agent to analyze: `claude`, `codex`, or `auto` (every agent whose root exists); default `claude` |
| `--input` | session root to scan (default: the source's own root — `~/.claude/projects` or `~/.codex/sessions`); ignored with `--source auto` |
| `--out` | HTML report path (default `report.html`) |
| `--open` | open the report in your browser when done |
| `--json PATH` | also write the summary JSON artifact |
| `--data-dir DIR` | also write per-facet files (`INDEX.md` · `<facet>.json` · `advice.txt`) for agents to `cat` |
| `--today` / `--one-week` / `--one-month` / `--all` | period presets (local-midnight aligned) |
| `--since ISO` | only events at/after this local date/datetime (exclusive with presets) |
| `--project SUBSTR` | only project directories whose name contains SUBSTR |
| `--redact-paths` | hash directories in reported paths (for sharing) |
| `--no-cache` | bypass the extraction digest cache |
| `--config PATH` / `--no-config` | advice-threshold overrides / ignore the default config |

The first run can take a dozen-odd seconds depending on corpus size, but a file
cache makes later runs fast — only changed files are re-read.

## 4. Report

The report is summary cards + Advice + diagnostic sections.

### Top cards

- `volume` — total tokens, new spend, cache reuse, tool activity, peak day, model mix.
- `waste signals` — tool pollution, waste signals, parse warnings. They turn a warning color when nonzero and jump to the matching section on click.

### Advice

A section that turns data inferred as waste into actionable advice.

- Each item carries a level (info / warn / critical) and its rule definition, escalating to critical past a multiple of the threshold.
- Skills and tools an advice item targets get a warning color in the graphs too, so the list and the graphs agree.
- Per-rule toggles, a min-level filter, a rule catalog, and a what-if threshold explorer.

### Diagnostic sections

Each looks at one axis of waste.

- `Daily tokens` — tokens per day. Saturation = new spend, muted = cache reuse.
- `Tool pollution ranking` — tools ranked by context re-entered (result bytes).
- `Skill & subagent chains` — tokens per skill/subagent. Click a row for its tool composition.
- `Duplicate reads` — files read repeatedly across sessions.
- `Projects` — per-project rollup (labelled by the real working-directory cwd).
- `Sessions` — per-session stats (sortable, cache efficiency, waste flags).

The report holds aggregated numbers only — no prompts, tool output, or file contents.

## 5. Agent facet files (`--data-dir`)

If the HTML report is for humans, `--data-dir DIR` also hands the same data to
agents as files. Each summary facet lands in its own file, so a routine can `cat`
just the piece it needs without parsing the whole thing.

- `INDEX.md` — what each file holds + headline numbers.
- `<facet>.json` — one file per summary key (`totals` · `by_project` · `sessions` · `advice` …).
- `advice.txt` — advice as plain lines, no JSON parsing.

## 6. Personal config

To persist tuned advice thresholds, save a JSON config. The report's what-if
`copy` button produces this snippet:

```jsonc
// ~/.config/claudeye/config.json
{ "advice": { "skill_min_turns": 3, "skill_new_spend_per_turn": 30000 } }
```

> Only listed keys override; typos fall back to defaults. Every `AdviceConfig`
> field is tunable this way, and the rule definitions and report follow the
> config so they never drift.

## 7. Metric

Each metric is labelled with one of three confidence levels.

- `measured` — tokens (deduped by line uuid + message id), tool calls, result bytes, cache efficiency, subagent-type attribution.
- `inferred` — duplicate reads, fork attribution, advice remedies.
- `approximate` — per-tool token attribution is not done by design (usage is per API response).

## 8. Docs

- [concept](docs/concept.md) — motivation and scope.
- [architecture](docs/architecture.md) — the layered design.

## 9. Development · contributing

The runtime is dependency-free; dev tooling is managed with [uv](https://docs.astral.sh/uv/).

```bash
make sync     # install dev tools (ruff · mypy · pytest)
make check    # the CI gate: lint + mypy + test
make report   # generate report.html and open it
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to contribute and the project principles.

## 10. License

[MIT](LICENSE).
