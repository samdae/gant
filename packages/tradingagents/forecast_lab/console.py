"""Boot the full workspace API inside the dedicated Forecast Lab service process."""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg import Error
from psycopg.conninfo import conninfo_to_dict
from starlette.staticfiles import StaticFiles


def checked_dsn(raw, database, user=None):
    try:
        cfg = conninfo_to_dict(raw or "")
    except Error:
        raise ValueError(
            "Invalid protected Forecast Lab database configuration"
        ) from None
    if (
        cfg.get("host") != "127.0.0.1"
        or cfg.get("port") != "55436"
        or cfg.get("dbname") != database
        or not cfg.get("user")
        or not cfg.get("password")
        or (user and cfg["user"] != user)
        or set(cfg) - {"host", "port", "dbname", "user", "password"}
    ):
        raise ValueError(
            "Expected the dedicated loopback Forecast Lab database and service identity"
        )
    return cfg


def configure_runtime(root, lab_env):
    """Called only from a new, integrated serve process, before importing any project config."""
    root = root.resolve()
    if lab_env.resolve() != root / "lab.env":
        raise ValueError("Integrated service requires its protected lab.env")
    if "tradingagents.default_config" in sys.modules:
        raise RuntimeError("Console must be configured in a fresh process")
    lab = dotenv_values(lab_env, interpolate=False)
    secret = dotenv_values(root / "console.env", interpolate=False)
    checked_dsn(lab.get("FORECAST_LAB_DSN"), "forecast_lab_research")
    dsn = secret.get("FORECAST_LAB_CONSOLE_DSN")
    checked_dsn(dsn, "forecast_lab_console", "forecast_lab_console_app")
    token = secret.get("TRADINGAGENTS_ADMIN_TOKEN")
    if not token or not token.strip():
        raise ValueError("Protected console administrator token required")

    # Never resolve inherited app configuration, PostgreSQL services/password files or a checkout .env.
    for key in tuple(os.environ):
        if key.startswith(
            (
                "SUPABASE_",
                "POSTGRES_",
                "PG",
                "TRADINGAGENTS_",
                "PORTFOLIO_",
                "FORECAST_LAB_",
                "OPENAI_",
                "ALPHA_VANTAGE_",
                "LANGCHAIN_",
                "LANGSMITH_",
            )
        ) or key in {"DATABASE_URL", "LLM_PROVIDER", "CODEX_MODEL", "RAG_TOP_K"}:
            os.environ.pop(key)
    for key, value in lab.items():
        if key.startswith("FORECAST_LAB_") and value is not None:
            os.environ[key] = value
    work = root / "console"
    work.mkdir(exist_ok=True)
    os.chdir(work)
    os.environ.update(
        FORECAST_LAB_STATE_DIR=str(root),
        TRADINGAGENTS_DB_URL=dsn,
        TRADINGAGENTS_ADMIN_TOKEN=token,
        TRADINGAGENTS_CHROMA_PATH=str(work / "chroma"),
        TRADINGAGENTS_SCHEDULER_ENABLED="true",
        PORTFOLIO_ENABLED="true",
        LLM_PROVIDER="codex",
        CODEX_MODEL=lab.get("FORECAST_LAB_MODEL") or "gpt-6.2-sol",
        TRADINGAGENTS_CORS_ORIGINS="http://127.0.0.1:8024,http://localhost:8024",
        PYTHON_DOTENV_DISABLED="1",
    )
    from tradingagents.default_config import DEFAULT_CONFIG

    DEFAULT_CONFIG.update(
        project_dir=str(work), data_cache_dir=str(work / "dataflows" / "data_cache")
    )
    from .engine import _configure_yahoo_cache

    _configure_yahoo_cache()
    from tradingagents.api.app import app

    return app


def console_ready():
    from tradingagents.api import app as console

    if (
        not console.scheduler
        or not console.scheduler.is_running()
        or not console.queue_worker_task
        or console.queue_worker_task.done()
    ):
        return False
    # Health probes run in the web thread pool; release their connection immediately.
    with psycopg.connect(
        console.scheduler.db.db_url, connect_timeout=3, autocommit=True
    ) as conn:
        identity = conn.execute("SELECT current_database(),current_user").fetchone()
    return identity == ("forecast_lab_console", "forecast_lab_console_app")


def mount_frontend(app, dist):
    dist = Path(dist).resolve()
    if not (dist / "index.html").is_file():
        raise RuntimeError(
            "Build apps/web/dist before starting the integrated workspace"
        )
    # The workspace router uses hash URLs. Only files in the build root are public.
    app.mount("/", StaticFiles(directory=dist, html=True), name="workspace-shell")
