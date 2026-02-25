# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

G-ANT is an AI-powered stock trading analysis system with 12 AI agents. See `README.md` for full details.

### Services

| Service | Port | How to start |
|---------|------|-------------|
| PostgreSQL 17 | 5432 | `docker compose -f infra/docker-compose.local.yml up -d` (or `scripts/run-db.sh`) |
| FastAPI Backend | 8000 | `scripts/run_api.sh` (auto-runs `uv sync` + uvicorn) |
| Svelte Frontend | 5173 | `scripts/run-fe.sh` (auto-runs `npm install` + vite dev) |

### Key gotchas

- **Docker daemon**: Must start `dockerd` before running PostgreSQL. In nested container environments (Cloud Agent VMs), Docker requires `fuse-overlayfs` storage driver and `iptables-legacy`. See daemon config at `/etc/docker/daemon.json`.
- **Environment variables**: Copy `.env.example` to `.env` and set at minimum `TRADINGAGENTS_ADMIN_TOKEN`. Local Postgres defaults: `POSTGRES_USER=trading`, `POSTGRES_PASSWORD=tradingpass`, `POSTGRES_DB=tradingagents`.
- **DB schema init**: Schema auto-initializes on API startup. Manual init: `.venv/bin/python scripts/init_db.py`.
- **`PYTHONPATH`**: The `run_api.sh` script sets `PYTHONPATH` to include both the repo root and `packages/` dir. When running uvicorn manually: `PYTHONPATH=/workspace:/workspace/packages`.
- **LLM provider**: Requires Google Gemini OAuth. For headless/CI, set `GEMINI_CLI_REFRESH_TOKEN` in `.env`. Without it, the 12 AI agents cannot run analysis, but the API and dashboard still function for CRUD operations.
- **No dedicated lint/test config**: The project has no eslint, pytest, or ruff configuration. Frontend lint is via `svelte-check` (`npm run check` in `apps/web/`). There is one pre-existing TS error in `Live.svelte`.
- **API routes have no `/api/` prefix**: Routes are at root (e.g., `/positions`, `/schedules`, `/metrics`), not `/api/positions`.
- **Package managers**: Backend uses `uv` (lockfile: `uv.lock`), frontend uses `npm` (lockfile: `package-lock.json`).
