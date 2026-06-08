#!/usr/bin/env bash
# One-time setup for ClearPort — fully offline (no API keys, no cloud, no Docker).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "ClearPort setup — offline by default (no API keys, no cloud)"
echo "Repo: $(pwd)"

# 1) Python
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.12+ not found. Install from https://www.python.org/downloads/" >&2
  exit 1
fi
PYVER="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
echo "  Python ${PYVER} detected"
python3 -c 'import sys; sys.exit(0 if sys.version_info[:2] >= (3,12) else 1)' \
  || { echo "Python 3.12+ required (found ${PYVER})." >&2; exit 1; }

# 2) .env (offline defaults need no keys)
if [ ! -f .env ]; then cp .env.example .env; echo "  created .env (offline defaults)"; else echo "  .env exists — left untouched"; fi

# 3) Backend dependencies
if command -v uv >/dev/null 2>&1; then
  echo "  Installing backend dependencies via uv…"
  uv sync --extra dev
else
  echo "  'uv' not found — using a venv + pip…"
  [ -d .venv ] || python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip
  ./.venv/bin/python -m pip install -e ".[dev]"
fi

# 4) Dashboard dependencies
if command -v npm >/dev/null 2>&1; then
  echo "  Installing dashboard dependencies via npm…"
  ( cd dashboard && { [ -f .env.local ] || cp .env.local.example .env.local; } && npm install )
else
  echo "  Node.js/npm not found — dashboard skipped. Install Node 18+ from https://nodejs.org" >&2
fi

echo
echo "Setup complete. Next:"
echo "  ./tools/start.sh        # backend (:8080) + dashboard (:3000)"
echo "  ./tools/verify.sh       # offline compile + tests"
echo "  uv run clearport-demo   # narrated console demo"
