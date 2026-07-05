# claudeye — Claude Code guide

Local, zero-dependency analyzer of Claude Code transcripts (dev tooling via uv).
Conventions and project principles: [CONTRIBUTING.md](CONTRIBUTING.md).

Gate before a PR:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy claudeye && uv run pytest
```

## Task and Issue Management

Every unit of work is tracked as one GitHub issue — the durable source of truth
that persists and is shared across sessions. **Every PR must reference an issue.**
Open one first if it does not exist yet; issue-less PRs are not accepted, even
for small fixes.

1. Open an issue for the unit of work (`gh issue create`) → `#N`.
2. Branch `feature/<N>-<slug>`; each unit lands as one squashed commit.
3. Commit `(#N) <type>: <summary>` (from v0.1 — see [CONTRIBUTING.md](CONTRIBUTING.md)
   for the format).
4. Open a PR with `Closes #N` in the body so the issue auto-closes on merge.

If your agent keeps an internal task list, it is an ephemeral per-session view;
link it to the issue by carrying `#N` in the task and commits — its local IDs
are not expected to match issue numbers.

## Codex Review Request Policy

Work is task-scoped: each task lands as one squashed commit. When creating the
PR, judge the task by its commit type and the domains it touched.

- **Skip Codex** for `docs` / `style` / `chore` / test-only tasks, and for
  render-only changes (`claudeye/render/**` — template, HTML, CSS, JS).
- **Request Codex** for `feat` / `fix` / `refactor` / `perf` that touch
  correctness, security, concurrency, transaction boundaries, the summary-JSON
  contract, the digest schema, the CLI/API surface, data-loss, or regression
  risk. Higher-risk domains: `claudeye/ingest/**` (parser, digest cache/schema),
  `claudeye/analyze/**` (dedup, summary, cost), `claudeye/domain/**` (value
  objects, pricing).

When a task warrants it, add a trailer to its squash commit (alongside
`Co-Authored-By:`):

```
Codex-Review: <reasons>   # e.g. schema-change, regression, data-loss, api-contract, security
```

After opening the PR, if its commit carries a `Codex-Review:` trailer, comment
on the PR:

```
@codex review
```

Otherwise do not mention Codex. Never request Codex for formatting, naming,
style, lint, or minor refactoring — CodeRabbit and human review cover those.
Codex's reviewer role is defined in [AGENTS.md](AGENTS.md).
