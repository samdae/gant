#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH" >&2
  exit 1
fi

if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  . "$SCRIPT_DIR/.env"
  set +a
fi

COMPOSE_FILE="$SCRIPT_DIR/docker-compose.local.yml"

docker compose -f "$COMPOSE_FILE" up -d
echo "Local Postgres is running on port 5432"
