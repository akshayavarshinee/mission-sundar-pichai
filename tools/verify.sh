#!/usr/bin/env bash
# Offline verification: byte-compile everything + run the full test suite.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "1/2  Byte-compiling backend + tests…"
python3 -m compileall -q clearport tests
echo "     COMPILE_OK"

echo "2/2  Running the test suite (offline, deterministic)…"
if command -v uv >/dev/null 2>&1; then
  uv run pytest -ra
elif [ -x ./.venv/bin/python ]; then
  ./.venv/bin/python -m pytest -ra
else
  echo "No environment found. Run ./tools/setup.sh first." >&2
  exit 1
fi
echo
echo "Verification complete."
