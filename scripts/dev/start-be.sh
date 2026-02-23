#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

export POSTGRES_USER=trading
export POSTGRES_PASSWORD=tradingpass
export POSTGRES_DB=tradingagents_dev
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5433
export TRADINGAGENTS_CORS_ORIGINS=http://localhost:5174
export TRADINGAGENTS_LOG_LEVEL=${TRADINGAGENTS_LOG_LEVEL:-INFO}

echo "[dev] Starting FastAPI on port 8001..."
uv run uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8001 --reload
