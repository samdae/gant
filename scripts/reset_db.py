#!/usr/bin/env python3
"""Reset database: DROP all tables (FK-safe order) + clear ChromaDB, then re-init schema.

Usage:
    python scripts/reset_db.py --confirm          # full reset
    python scripts/reset_db.py --confirm --keep-chroma  # DB only, keep vectors
"""
import argparse
import os
import shutil
import sys
from pathlib import Path


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        os.environ.setdefault(key, value)


def get_database_url() -> str:
    for key in ("SUPABASE_DB_URL", "TRADINGAGENTS_DB_URL", "DATABASE_URL"):
        value = os.getenv(key)
        if value:
            return value

    user = os.getenv("POSTGRES_USER")
    password = os.getenv("POSTGRES_PASSWORD")
    database = os.getenv("POSTGRES_DB")
    if not (user and password and database):
        return ""

    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


# FK-safe: children first. v6 adds rag_validation_results, retrospective_analyses, portfolio_*.
DROP_ORDER = [
    "rag_validation_results",    # refs retrospective_analyses, reflections
    "retrospective_analyses",    # refs positions
    "reflections",
    "trades",
    "reports",
    "schedule_job_events",
    "schedule_jobs",
    "positions",
    "portfolio_trades",          # refs portfolio_decisions
    "portfolio_decisions",      # refs portfolio_configs
    "portfolio_holdings",       # refs portfolio_configs
    "portfolio_reflections",    # refs portfolio_configs
    "portfolio_configs",
    "schedules",                # legacy (may not exist)
    "schedule_configs",
]


def reset_postgres(db_url: str) -> None:
    import psycopg

    conn = psycopg.connect(db_url, connect_timeout=5)
    conn.autocommit = True

    for table in DROP_ORDER:
        conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        print(f"  dropped {table}")

    conn.close()


def reset_chromadb(repo_root: Path) -> None:
    chroma_path = os.getenv(
        "TRADINGAGENTS_CHROMA_PATH",
        str(repo_root / "packages" / "tradingagents" / "memory" / "chroma"),
    )
    if os.path.isdir(chroma_path):
        shutil.rmtree(chroma_path)
        print(f"  removed {chroma_path}")
    else:
        print(f"  chroma dir not found ({chroma_path}), skipping")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reset G-ANT database")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required flag to prevent accidental execution",
    )
    parser.add_argument(
        "--keep-chroma",
        action="store_true",
        help="Skip ChromaDB reset (PostgreSQL only)",
    )
    args = parser.parse_args()

    if not args.confirm:
        print("ERROR: pass --confirm to execute reset", file=sys.stderr)
        return 1

    repo_root = Path(__file__).resolve().parents[1]
    packages_dir = repo_root / "packages"
    sys.path.insert(0, str(packages_dir))
    load_dotenv(repo_root / ".env")

    db_url = get_database_url()
    if not db_url:
        print("ERROR: Database URL is not configured", file=sys.stderr)
        return 1

    print("[1/3] Dropping PostgreSQL tables...")
    reset_postgres(db_url)

    if not args.keep_chroma:
        print("[2/3] Clearing ChromaDB...")
        reset_chromadb(repo_root)
    else:
        print("[2/3] Skipping ChromaDB (--keep-chroma)")

    print("[3/3] Re-initializing schema...")
    from tradingagents.storage import Database

    db = Database(db_url)
    db.init_schema()

    print("Reset complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
