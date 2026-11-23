#!/usr/bin/env python3
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    packages_dir = repo_root / "packages"
    sys.path.insert(0, str(packages_dir))
    load_dotenv(os.getenv("TRADINGAGENTS_ENV_FILE", repo_root / ".env"))

    from tradingagents.default_config import get_database_url

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
