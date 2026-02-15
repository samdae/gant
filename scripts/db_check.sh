#!/bin/sh
set -eu

DB_PATH="${1:-/home/azdev/.openclaw/workspace/TradingAgents/tradingagents/memory/trading.db}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 not found in PATH" >&2
  exit 1
fi

sqlite3 "$DB_PATH" <<'SQL'
.headers on
.mode column

SELECT 'schedule_configs' AS table, COUNT(*) AS rows FROM schedule_configs;
SELECT * FROM schedule_configs ORDER BY created_at DESC LIMIT 20;

SELECT 'schedules' AS table, COUNT(*) AS rows FROM schedules;
SELECT * FROM schedules ORDER BY created_at DESC LIMIT 20;

SELECT 'schedule_jobs' AS table, COUNT(*) AS rows FROM schedule_jobs;
SELECT * FROM schedule_jobs ORDER BY created_at DESC LIMIT 20;
SQL
