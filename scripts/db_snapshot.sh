#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DB_PATH="${1:-$ROOT_DIR/packages/tradingagents/memory/trading.db}"
SNAPSHOT_PATH="${2:-/tmp/trading_snapshot.db}"
MAX_RETRY="${MAX_RETRY:-5}"
SLEEP_SEC="${SLEEP_SEC:-1}"

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 not found in PATH" >&2
  exit 1
fi

attempt=1
while [ "$attempt" -le "$MAX_RETRY" ]; do
  if sqlite3 "$DB_PATH" <<SQL
.timeout 5000
.backup "$SNAPSHOT_PATH"
SQL
  then
    echo "Snapshot created: $SNAPSHOT_PATH"
    exit 0
  fi

  echo "Backup failed (attempt $attempt/$MAX_RETRY). Retrying..." >&2
  attempt=$((attempt + 1))
  sleep "$SLEEP_SEC"
done

echo "Backup failed after $MAX_RETRY attempts. Stop backend and retry." >&2
exit 1
