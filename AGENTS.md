# AGENTS.md

## Cursor Cloud specific instructions

### Project Overview

G-ANT is a multi-agent AI trading analysis system. Monorepo with:
- **Backend (BE):** `packages/tradingagents/` — Python 3.11, FastAPI, LangGraph, psycopg (raw SQL), ChromaDB
- **Frontend (FE):** `apps/web/` — Svelte 4, TypeScript, Vite

### Prerequisites

- **Docker** must be running for PostgreSQL 17 (container: `tradingagents-postgres`)
- **uv** manages Python dependencies (lockfile: `uv.lock`, venv: `.venv` with Python 3.11)
- **npm** manages FE dependencies (lockfile: `apps/web/package-lock.json`)

### Starting Services

1. **PostgreSQL:** `docker compose -f infra/docker-compose.local.yml up -d` (port 5432). See `scripts/run-db.sh`.
2. **Init DB schema** (first time or after schema changes):
   ```
   PYTHONPATH="packages" .venv/bin/python scripts/init_db.py
   ```
   **Gotcha:** If `init_db.py` hangs, check for stale Postgres connections holding locks. Terminate them via:
   ```
   docker exec tradingagents-postgres psql -U trading -d tradingagents -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='tradingagents' AND pid != pg_backend_pid();"
   ```
3. **Backend API:** Source `.env` first, then:
   ```
   set -a && . .env && set +a && PYTHONPATH="packages" .venv/bin/python -m uvicorn tradingagents.api.app:app --host 0.0.0.0 --port 8000
   ```
   Requires `TRADINGAGENTS_ADMIN_TOKEN` env var (set in `.env`).
4. **Frontend dev server:** `cd apps/web && npm run dev` (default port 5173)

### Lint / Check / Build

- **FE type check:** `cd apps/web && npx svelte-check --tsconfig ./tsconfig.json` (2 pre-existing TS errors, 11 a11y warnings)
- **FE build:** `cd apps/web && npm run build`
- **BE:** No formal linter configured. Verify with `PYTHONPATH="packages" .venv/bin/python -c "import tradingagents"` for import sanity.
- **No test suite** exists in this repo currently.

### Environment Variables

`.env` in workspace root is used by both `scripts/run_api.sh` and direct uvicorn startup. Key vars:
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
- `TRADINGAGENTS_ADMIN_TOKEN` (required for write API endpoints)
- `TRADINGAGENTS_SCHEDULER_ENABLED` (set `false` for dev to avoid triggering LLM calls)
- `LLM_PROVIDER` — `gemini-cli` (default), `antigravity`, or `codex`. Requires OAuth setup.

### Key Gotchas

- The `run_api.sh` script targets `apps.api.app:app` (an older path). Use `tradingagents.api.app:app` for the current module path.
- Backend startup initializes the DB schema automatically, so `init_db.py` is only needed when running outside the API.
- ChromaDB data is stored locally at `packages/tradingagents/memory/chroma/` by default.
- Scheduler is disabled by default in `.env` (`TRADINGAGENTS_SCHEDULER_ENABLED=false`). Running a full analysis cycle requires LLM OAuth credentials.
