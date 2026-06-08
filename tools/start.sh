#!/usr/bin/env bash
# Start ClearPort locally — backend API (:8080) and dashboard (:3000), offline.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ROOT="$(pwd)"

# Pick the backend runner: uv > venv console-script > module.
if command -v uv >/dev/null 2>&1; then
  BACKEND=(uv run clearport-api)
elif [ -x ./.venv/bin/clearport-api ]; then
  BACKEND=(./.venv/bin/clearport-api)
elif [ -x ./.venv/bin/python ]; then
  BACKEND=(./.venv/bin/python -m clearport.api.main)
else
  echo "No backend environment found. Run ./tools/setup.sh first." >&2
  exit 1
fi

echo "Starting backend → http://localhost:8080 (docs at /docs)"
"${BACKEND[@]}" &
BACKEND_PID=$!

DASH_PID=""
if command -v npm >/dev/null 2>&1; then
  echo "Starting dashboard → http://localhost:3000"
  ( cd dashboard && npm run dev ) &
  DASH_PID=$!
else
  echo "npm not found — backend only. Open http://localhost:8080/docs" >&2
fi

trap 'echo; echo "Stopping…"; kill "$BACKEND_PID" ${DASH_PID:+"$DASH_PID"} 2>/dev/null || true' INT TERM
echo "Tip: in the dashboard, click '▶ Play full demo'. Press Ctrl+C to stop."
wait
