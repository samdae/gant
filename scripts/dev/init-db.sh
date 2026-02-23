#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

export POSTGRES_USER=trading
export POSTGRES_PASSWORD=tradingpass
export POSTGRES_DB=tradingagents_dev
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5433

echo "[dev] Initializing DB schema..."
python scripts/init_db.py

echo "[dev] Schema initialization complete"
