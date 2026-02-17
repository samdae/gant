#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not in PATH" >&2
  exit 1
fi

if [ -f "$ROOT_DIR/.env" ]; then
  set -a
  . "$ROOT_DIR/.env"
  set +a
fi

COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.local.yml"
CONTAINER_NAME="tradingagents-postgres"

EXISTING_ID=$(docker ps -a --filter "name=^/${CONTAINER_NAME}$" --format "{{.ID}}")
if [ -n "$EXISTING_ID" ]; then
  STATUS=$(docker inspect -f "{{.State.Status}}" "$CONTAINER_NAME")
  if [ "$STATUS" = "running" ]; then
    echo "Local Postgres container is already running"
  else
    docker start "$CONTAINER_NAME" >/dev/null
    echo "Local Postgres container started"
  fi
  exit 0
fi

docker compose -f "$COMPOSE_FILE" up -d
echo "Local Postgres is running on port 5432"
