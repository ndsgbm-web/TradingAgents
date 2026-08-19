#!/bin/zsh
# TradingAgents web UI launcher.
# Usage: ./webapp/start.sh [--port 8000]

set -e
cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
if [[ "$1" == "--port" && -n "$2" ]]; then
  PORT="$2"
fi

if [[ ! -d .venv ]]; then
  echo "missing .venv — run: uv venv && uv pip install -e ." >&2
  exit 1
fi

source .venv/bin/activate
echo "Starting TradingAgents web UI on http://127.0.0.1:${PORT}"
echo "Press Ctrl+C to stop."
exec uvicorn webapp.server:app --host 127.0.0.1 --port "${PORT}"
