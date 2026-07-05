#!/usr/bin/env bash
# claudeye installer — install the `claudeye` command from the repo.
# Runtime is zero-dependency (standard library only); this just puts the
# package on your PATH via uv, pipx, or pip — whichever you have.
#
#   curl -fsSL https://raw.githubusercontent.com/L2zz/claudeye/main/install.sh | bash
#
# Honors:
#   CLAUDEYE_REF   git ref/branch/tag to install (default: main)

set -euo pipefail

REPO="${CLAUDEYE_REPO:-L2zz/claudeye}"
REF="${CLAUDEYE_REF:-main}"
SPEC="git+https://github.com/${REPO}@${REF}"

if command -v uv >/dev/null 2>&1; then
  echo "installing claudeye with uv tool ($REPO@$REF) …"
  uv tool install --force "$SPEC"
elif command -v pipx >/dev/null 2>&1; then
  echo "installing claudeye with pipx ($REPO@$REF) …"
  pipx install --force "$SPEC"
elif command -v pip3 >/dev/null 2>&1; then
  echo "installing claudeye with pip ($REPO@$REF) …"
  pip3 install --user --upgrade "$SPEC"
else
  echo "error: need one of uv, pipx, or pip3 to install" >&2
  echo "       (get uv: https://docs.astral.sh/uv/)" >&2
  exit 1
fi

echo "installed. try:  claudeye --today --open"
