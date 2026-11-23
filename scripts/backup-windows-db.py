"""Back up the active native Windows database using the application's credentials."""
import os
import subprocess
from tempfile import mkdtemp
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values


def main():
    project = Path(__file__).resolve().parents[1]
    config = dotenv_values(project / ".env")
    tools = Path(os.environ["LOCALAPPDATA"]) / "TradingAgentsDeploy/pgsql/bin"
    parent = project.parent / "TradingAgents-backups"
    parent.mkdir(exist_ok=True)
    folder = Path(mkdtemp(prefix=datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=parent))
    target = folder / "tradingagents_dev.dump"
    temporary = target.with_suffix(".partial")
    env = {**os.environ, "PGPASSWORD": config["POSTGRES_PASSWORD"]}
    subprocess.run([
        tools / "pg_dump.exe", "-Fc", "-h", config["POSTGRES_HOST"], "-p", config["POSTGRES_PORT"],
        "-U", config["POSTGRES_USER"], "-d", config["POSTGRES_DB"], "-f", temporary,
    ], env=env, check=True)
    subprocess.run([tools / "pg_restore.exe", "-f", os.devnull, temporary], check=True)
    temporary.rename(target)
    print(target)


if __name__ == "__main__":
    main()
