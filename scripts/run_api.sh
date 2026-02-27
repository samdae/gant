#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
VENV_DIR="$ROOT_DIR/.venv"
PYTHON_VERSION="${TRADINGAGENTS_PYTHON_VERSION:-3.11}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed. Install it first: https://docs.astral.sh/uv/" >&2
  exit 1
fi

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

if [ -z "${TRADINGAGENTS_ADMIN_TOKEN:-}" ]; then
  echo "TRADINGAGENTS_ADMIN_TOKEN is required. Set it in .env or the shell." >&2
  exit 1
fi

if [ -d "$VENV_DIR" ]; then
  CURRENT_PY=$(
    "$VENV_DIR/bin/python" -c 'import sys; print(".".join(map(str, sys.version_info[:2])))' 2>/dev/null || echo ""
  )
  if [ "$CURRENT_PY" != "$PYTHON_VERSION" ]; then
    echo "Existing venv uses Python ${CURRENT_PY:-unknown}. Recreating with Python $PYTHON_VERSION." >&2
    rm -rf "$VENV_DIR"
  fi
fi

if [ ! -d "$VENV_DIR" ]; then
  uv venv --python "$PYTHON_VERSION" "$VENV_DIR"
fi

export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/packages${PYTHONPATH:+:$PYTHONPATH}"

cd "$ROOT_DIR"
unset VIRTUAL_ENV
uv sync --python "$VENV_DIR/bin/python"

mkdir -p "$ROOT_DIR/logs"
exec "$VENV_DIR/bin/python" -m uvicorn apps.api.app:app --host 0.0.0.0 --port 8000 \
  --log-config "$SCRIPT_DIR/log_config.json"
