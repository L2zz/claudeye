# Contributing

Thanks for your interest in claudeye. Issues and PRs of any size are welcome.

## Getting started

**The runtime is dependency-free** — users only need Python 3.9+. Only the dev
tooling (tests, lint, type-check) is managed with [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/L2zz/claudeye
cd claudeye
uv sync --extra dev             # install dev tools (ruff · mypy · pytest)
uv run pytest                   # tests (python3 -m unittest discover -s tests also works)
uv run claudeye --today --open  # run locally (python -m claudeye also works)
```

## The dev gate (same as CI)

A PR must pass these four. Running `pre-commit install` locally runs the first
three on every commit.

```bash
uv run ruff check .            # lint
uv run ruff format --check .   # format
uv run mypy claudeye           # type-check
uv run pytest                  # tests
```

The CodeRabbit bot reviews PRs automatically (architecture and logic; style is
handled by the gate above). Its review rules are spelled out in `.coderabbit.yaml`.

## Project principles (check before a PR)

claudeye keeps a few principles on purpose. Please discuss first before a change
that alters them.

- **Zero dependencies** — standard library only. The HTML report is
  self-contained too (no external CDN, fonts, or scripts; every value is injected
  via `textContent`, so it is XSS-safe).
- **No raw text** — prompts, tool output, and file contents never reach the
  report by any path. Aggregated numbers only.
- **No cost estimation** — the report tracks context waste, not spend. Cost math
  (even approximate) is out of scope; use ccusage for cost.
- **measured / inferred / approximate kept separate** — new metrics carry a
  confidence label. Measured and estimated values are never blended.

## Code style

- New public APIs get a docstring (purpose → role → implementation, side effects noted).
- Domain data structures are ordered so the most important fields read first.
- New behavior ships with tests; add fixtures under `tests/fixtures` matching the real schema.

## Commits

- Commit in **logical units** (docs / feature / tests, by role and step). Don't
  mix unrelated changes into one commit.
- Use **Conventional Commits (English)** — the subject is `type: subject`
  (English, imperative, concise), with the "what and why" in the body. Types:
  `feat` · `fix` · `refactor` · `docs` · `test` · `chore`, etc.
- Add a `Co-Authored-By` trailer for AI pair work.
- **Issue linking (from v0.1)** — from the v0.1 release on, open an issue first
  and link the commit with a `(#N)` subject prefix and a `Closes #N` footer.
  Pre-v0.1 commits follow the format above without issue references.

```text
# pre-v0.1
feat(render): add a project rollup section to the report

Group per-session stats by project so a multi-repo corpus is legible at a
glance, ranked by total tokens.

Co-Authored-By: ...

# from v0.1
(#42) feat(render): add a project rollup section to the report

...body...

Closes #42
Co-Authored-By: ...
```

## PRs

- **Issue first (required)** — every PR must reference a GitHub issue. Open one
  first for the unit of work (create it if none exists), and put `Closes #N` in
  the PR body so the issue auto-closes on merge. **PRs without an issue are not
  accepted** — even small fixes start with an issue.
- Say what changed and why, and how you verified it.
- Confirm the tests pass (`python3 -m unittest discover -s tests`).
- For a UI change, note what you saw when you actually opened the report — it
  speeds up review.

## Code of Conduct

Be respectful. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for the details.
