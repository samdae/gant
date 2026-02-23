#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../../apps/web"

export VITE_API_BASE_URL=http://localhost:8001

echo "[dev] Starting Vite on port 5174 (API → localhost:8001)..."
npm run dev -- --port 5174
