"""Create and read back a custom-format backup of the isolated Forecast Lab database."""

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from dotenv import dotenv_values
from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict


def credentials(lab, filename, field, database, user=None):
    config = dotenv_values(lab / filename, interpolate=False)
    try:
        db = conninfo_to_dict(config.get(field) or "")
    except ProgrammingError:
        raise SystemExit("Invalid Forecast Lab backup configuration") from None
    if (
        db.get("host") != "127.0.0.1"
        or db.get("port") != "55436"
        or db.get("dbname") != database
        or not db.get("user")
        or (user and db["user"] != user)
        or not db.get("password")
        or set(db) - {"host", "port", "dbname", "user", "password"}
    ):
        raise SystemExit("Expected dedicated Forecast Lab database credentials")
    return db


def backup(lab, tools, db):
    backups = lab / "backups"
    backups.mkdir(exist_ok=True)
    if backups.resolve() != lab.resolve() / "backups":
        raise SystemExit("Backup directory must be inside the protected lab runtime")
    prefix = datetime.now(UTC).strftime(f"{db['dbname']}-%Y%m%dT%H%M%SZ-")
    with NamedTemporaryFile(
        dir=backups, prefix=prefix, suffix=".partial", delete=False
    ) as tmp:
        partial = Path(tmp.name)
    target = partial.with_suffix(".dump")
    clean_env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
    try:
        subprocess.run(
            [tools / "pg_dump.exe", "-Fc", "--no-password", "-f", partial],
            env={
                **clean_env,
                "PGHOST": db["host"],
                "PGPORT": db["port"],
                "PGDATABASE": db["dbname"],
                "PGUSER": db["user"],
                "PGPASSWORD": db["password"],
                "PGOPTIONS": "-c default_transaction_read_only=on",
                "PGCONNECT_TIMEOUT": "10",
            },
            check=True,
        )
        subprocess.run(
            [tools / "pg_restore.exe", "-f", os.devnull, partial],
            env=clean_env,
            check=True,
        )
        partial.rename(target)
    finally:
        partial.unlink(missing_ok=True)
    print(target)


def main():
    local = Path(os.environ["LOCALAPPDATA"])
    lab = local / "TradingAgentsV3"
    tools = local / "TradingAgentsDeploy" / "pgsql" / "bin"
    databases = (
        credentials(lab, "lab.env", "FORECAST_LAB_DSN", "forecast_lab_research"),
        credentials(
            lab,
            "console.env",
            "FORECAST_LAB_CONSOLE_DSN",
            "forecast_lab_console",
            "forecast_lab_console_app",
        ),
    )
    for database in databases:
        backup(lab, tools, database)


if __name__ == "__main__":
    main()
