#!/usr/bin/env python3
import os
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


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    db_url = get_database_url()
    if not db_url:
        print("Database URL is not configured", file=sys.stderr)
        return 1

    from tradingagents.storage import Database

    db = Database(db_url)
    db.init_schema()
    print("Schema initialization complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
