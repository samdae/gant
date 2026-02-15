#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


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


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    dotenv_path = repo_root / ".env"
    load_dotenv(dotenv_path)

    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("SUPABASE_DB_URL is not set", file=sys.stderr)
        return 1

    try:
        parts = urlsplit(db_url)
        query = parse_qsl(parts.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in query if k.lower() != "pgbouncer"]
        if len(filtered) != len(query):
            db_url = urlunsplit(
                (parts.scheme, parts.netloc, parts.path, urlencode(filtered), parts.fragment)
            )
            print("Note: removed unsupported query param 'pgbouncer' for psycopg")
    except Exception:
        pass

    try:
        import psycopg
    except Exception as exc:
        print(f"psycopg import failed: {exc}", file=sys.stderr)
        return 2

    try:
        conn = psycopg.connect(db_url, connect_timeout=5)
    except Exception as exc:
        print(f"Connection failed: {exc}", file=sys.stderr)
        return 3

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT current_database(), current_user,
                       inet_server_addr(), inet_server_port(), version()
                """
            )
            row = cur.fetchone()
        print("Connection ok")
        print(f"database: {row[0]}")
        print(f"user: {row[1]}")
        print(f"server: {row[2]}:{row[3]}")
        print(f"version: {row[4]}")
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
