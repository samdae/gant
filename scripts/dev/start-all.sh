#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo " G-ANT Dev Environment (포트 분리)"
echo " DB: 5433 | BE: 8001 | FE: 5174"
echo "============================================"
echo ""

# 1. DB
bash start-db.sh

# 2. Init schema (최초 1회, 이미 있으면 무해)
bash init-db.sh

# 3. BE (background)
echo ""
echo "[dev] Starting Backend..."
bash start-be.sh &
BE_PID=$!

# 4. FE (foreground)
sleep 2
echo ""
echo "[dev] Starting Frontend..."
bash start-fe.sh

# cleanup
kill $BE_PID 2>/dev/null
