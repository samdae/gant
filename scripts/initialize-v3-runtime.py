"""Create the local GANT v3 Windows runtime once. Run with the checkout's .venv Python."""

import os
import secrets
import socket
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

import psycopg
from psycopg import sql

PORT = 55436
ADMIN = "gant_v3_admin"
DATABASES = {
    "forecast_lab_research": "forecast_lab_app",
    "forecast_lab_console": "forecast_lab_console_app",
    "forecast_lab_acceptance": "forecast_lab_test_app",
}


class SetupError(Exception):
    """Safe operator-facing diagnostic; never include a DSN, SQL statement or password."""


def restrict_directory(runtime):
    # Rebuild the DACL from scratch rather than relying on inherited profile permissions.
    cmd = """
$ErrorActionPreference = 'Stop'
$me = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$system = [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')
$acl = [System.Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
foreach ($sid in @($me, $system)) {
    $acl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new(
        $sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
}
[System.IO.Directory]::SetAccessControl($env:GANT_NEW_RUNTIME, $acl)
$actual = [System.IO.Directory]::GetAccessControl($env:GANT_NEW_RUNTIME)
$rules = $actual.GetAccessRules($true,$true,[System.Security.Principal.SecurityIdentifier])
if (!$actual.AreAccessRulesProtected -or $rules.Count -ne 2) { throw 'Unexpected runtime permissions' }
foreach ($sid in @($me, $system)) {
    if (!($rules | Where-Object { $_.IdentityReference -eq $sid -and
        $_.FileSystemRights -eq 'FullControl' -and $_.AccessControlType -eq 'Allow' -and
        [int]$_.InheritanceFlags -eq 3 })) { throw 'Missing inheritable full control' }
}
"""
    powershell = (
        Path(os.environ["SystemRoot"])
        / "System32/WindowsPowerShell/v1.0/powershell.exe"
    )
    subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", cmd],
        env={**os.environ, "GANT_NEW_RUNTIME": str(runtime)},
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
    )


def check_unused(runtime, port):
    if os.path.lexists(runtime):
        raise SetupError("Runtime directory already exists. Initialization refused.")
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            raise SetupError(
                "Database port is already in use or unavailable. Initialization refused."
            ) from None


@contextmanager
def isolated_libpq():
    inherited = {
        key: value for key, value in os.environ.items() if key.upper().startswith("PG")
    }
    try:
        for key in inherited:
            del os.environ[key]
        yield
    finally:
        os.environ.update(inherited)


def database_setup(data, port, passwords, admin_password):
    with psycopg.connect(
        host="127.0.0.1",
        port=port,
        user=ADMIN,
        dbname="postgres",
        password=admin_password,
        connect_timeout=5,
        autocommit=True,
    ) as conn:
        directory, address, actual_port, username = conn.execute(
            "SELECT current_setting('data_directory'),inet_server_addr()::text,inet_server_port(),current_user"
        ).fetchone()
        if Path(directory).resolve() != data.resolve() or (
            address,
            actual_port,
            username,
        ) != ("127.0.0.1/32", port, ADMIN):
            raise SetupError(
                "Database identity differs from the newly created cluster."
            )
        for name, role in DATABASES.items():
            conn.execute(
                sql.SQL(
                    "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}"
                ).format(sql.Identifier(role), sql.Literal(passwords[role]))
            )
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(name), sql.Identifier(role)
                )
            )
        for (name,) in conn.execute("SELECT datname FROM pg_database").fetchall():
            conn.execute(
                sql.SQL("REVOKE CONNECT ON DATABASE {} FROM PUBLIC").format(
                    sql.Identifier(name)
                )
            )
        for name, role in DATABASES.items():
            conn.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(name), sql.Identifier(role)
                )
            )
            conn.execute(
                sql.SQL("ALTER DATABASE {} SET timezone TO 'UTC'").format(
                    sql.Identifier(name)
                )
            )


def initialize(runtime, pg_bin, port=PORT):
    check_unused(runtime, port)
    initdb, pgctl = (pg_bin / f"{name}.exe" for name in ("initdb", "pg_ctl"))
    if not all(path.is_file() for path in (initdb, pgctl)):
        raise SetupError("PostgreSQL initdb and pg_ctl executables are required.")
    runtime.mkdir(exist_ok=False)
    restrict_directory(runtime)
    logs = runtime / "logs"
    logs.mkdir()
    (runtime / "console").mkdir()
    (runtime / "qa").mkdir()
    data = runtime / "pgdata"
    admin_password = secrets.token_urlsafe(36)
    admin_file = runtime / "cluster-admin.pw"
    admin_file.write_text(admin_password + "\n", encoding="ascii")
    clean = {k: v for k, v in os.environ.items() if not k.upper().startswith("PG")}
    with (logs / "initialize.log").open("ab") as log:

        def pg(command):
            subprocess.run(
                command,
                env=clean,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                timeout=100,
                check=True,
            )

        pg(
            [
                initdb,
                "-D",
                data,
                "-U",
                ADMIN,
                "--pwfile",
                admin_file,
                "--auth=scram-sha-256",
                "--encoding=UTF8",
                "--locale=C",
            ]
        )
        with (data / "postgresql.conf").open("a", encoding="ascii") as conf:
            conf.write(
                f"\nlisten_addresses='127.0.0.1'\nport={port}\ntimezone='UTC'\nlog_timezone='UTC'\npassword_encryption='scram-sha-256'\n"
            )
        pg([pgctl, "start", "-w", "-t", "45", "-D", data, "-l", logs / "postgres.log"])
        try:
            passwords = {role: secrets.token_urlsafe(36) for role in DATABASES.values()}
            with isolated_libpq():
                database_setup(data, port, passwords, admin_password)

            def dsn(db):
                role = DATABASES[db]
                return f"postgresql://{role}:{quote(passwords[role], safe='')}@127.0.0.1:{port}/{db}"

            (runtime / "lab.env").write_text(
                "FORECAST_LAB_DSN=" + dsn("forecast_lab_research") + "\n"
                "FORECAST_LAB_SCHEDULER_ENABLED=0\nFORECAST_LAB_LEGACY_REFERENCE=0\nFORECAST_LAB_MODEL=gpt-6.2-sol\n",
                encoding="ascii",
            )
            (runtime / "console.env").write_text(
                "FORECAST_LAB_CONSOLE_DSN="
                + dsn("forecast_lab_console")
                + "\nTRADINGAGENTS_ADMIN_TOKEN="
                + secrets.token_urlsafe(36)
                + "\n",
                encoding="ascii",
            )
            (runtime / "acceptance.env").write_text(
                "FORECAST_LAB_DSN=" + dsn("forecast_lab_acceptance") + "\n",
                encoding="ascii",
            )
        except BaseException:
            pg([pgctl, "stop", "-D", data, "-m", "fast", "-w", "-t", "45"])
            raise


def main():
    if os.name != "nt":
        raise SetupError("This command requires native Windows.")
    local = Path(os.environ["LOCALAPPDATA"])
    initialize(local / "TradingAgentsV3", local / "TradingAgentsDeploy/pgsql/bin")
    print(
        "GANT v3 PostgreSQL initialized on 127.0.0.1:55436. Scheduler and reference capture are disabled."
    )


if __name__ == "__main__":
    try:
        main()
    except SetupError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
    except Exception:  # noqa: BLE001 -- initialization errors may contain credentials
        print(
            "Initialization failed. Check the protected runtime and its logs before retrying.",
            file=sys.stderr,
        )
        sys.exit(1)
