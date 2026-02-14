#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_DIR="$SCRIPT_DIR/.venv"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  . "$SCRIPT_DIR/.env"
  set +a
fi

if [ -z "${TRADINGAGENTS_ADMIN_TOKEN:-}" ]; then
  echo "TRADINGAGENTS_ADMIN_TOKEN is required. Set it in .env or the shell." >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  uv venv "$VENV_DIR"
fi

exec uv run uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8000
