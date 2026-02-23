#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

echo "[dev] Starting PostgreSQL on port 5433..."
docker compose -f infra/docker-compose.dev.yml up -d

echo "[dev] Waiting for PostgreSQL..."
until docker exec tradingagents-postgres-dev pg_isready -U trading -d tradingagents_dev > /dev/null 2>&1; do
  sleep 1
done

echo "[dev] PostgreSQL ready (localhost:5433)"
