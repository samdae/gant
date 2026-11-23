"""Create and read back a custom-format backup of the isolated Forecast Lab database."""

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile

from dotenv import dotenv_values
from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict


def main():
    local = Path(os.environ["LOCALAPPDATA"])
    lab = local / "TradingAgentsForecastLab"
    tools = local / "TradingAgentsDeploy" / "pgsql" / "bin"
    config = dotenv_values(lab / "lab.env", interpolate=False)
    try:
        db = conninfo_to_dict(config.get("FORECAST_LAB_DSN") or "")
    except ProgrammingError:
        raise SystemExit("Invalid Forecast Lab backup configuration") from None
    if (
        db.get("host") != "127.0.0.1"
        or db.get("port") != "55434"
        or db.get("dbname") != "forecast_lab_research"
        or not db.get("user")
        or not db.get("password")
        or {"hostaddr", "service", "options"} & db.keys()
    ):
        raise SystemExit(
            "Expected the dedicated loopback Forecast Lab research database"
        )

    backups = lab / "backups"
    backups.mkdir(exist_ok=True)
    if backups.resolve() != lab.resolve() / "backups":
        raise SystemExit("Backup directory must be inside the protected lab runtime")
    prefix = datetime.now(UTC).strftime("forecast_lab_research-%Y%m%dT%H%M%SZ-")
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


if __name__ == "__main__":
    main()
