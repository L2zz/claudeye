# claudeye — dev & install helpers. Runtime is zero-dependency; dev tooling
# (ruff · mypy · pytest) is managed with uv.
.PHONY: help sync test lint check install uninstall report

help:
	@echo "claudeye make targets:"
	@echo "  make sync       install dev tools (uv sync --extra dev)"
	@echo "  make test       run the unit test suite"
	@echo "  make lint       ruff check + format --check"
	@echo "  make check      lint + mypy + test (the CI gate)"
	@echo "  make install    install the 'claudeye' command with uv tool"
	@echo "  make uninstall  remove the installed command"
	@echo "  make report     generate report.html from ~/.claude/projects and open it"

sync:
	uv sync --extra dev

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

check: lint
	uv run mypy claudeye
	uv run pytest

install:
	uv tool install --force .

uninstall:
	uv tool uninstall claudeye

report:
	uv run claudeye --open
