import importlib.util
import os
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg.conninfo import conninfo_to_dict

spec = importlib.util.spec_from_file_location(
    "v3_initialize",
    Path(__file__).resolve().parents[1] / "scripts/initialize-v3-runtime.py",
)
init = importlib.util.module_from_spec(spec)
spec.loader.exec_module(init)


@unittest.skipUnless(
    os.name == "nt" and os.environ.get("PG_TEST_BINDIR"),
    "local Windows PostgreSQL fixture",
)
class WindowsInitializeV3Tests(unittest.TestCase):
    def test_new_isolated_cluster_and_existing_refusal(self):
        bindir = Path(os.environ["PG_TEST_BINDIR"])
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp) / "v3"
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", 0))
                port = probe.getsockname()[1]
                with self.assertRaises(init.SetupError):
                    init.initialize(runtime, bindir, port)
            self.assertFalse(runtime.exists())
            init.initialize(runtime, bindir, port)
            try:
                with self.assertRaises(init.SetupError):
                    init.initialize(runtime, bindir, port)
                strings = []
                for envfile, dbname in [
                    ("lab.env", "forecast_lab_research"),
                    ("console.env", "forecast_lab_console"),
                    ("acceptance.env", "forecast_lab_acceptance"),
                ]:
                    values = dotenv_values(runtime / envfile, interpolate=False)
                    dsn = next(v for k, v in values.items() if k.endswith("_DSN"))
                    strings.append(dsn)
                    with psycopg.connect(dsn) as conn:
                        user, database, tz, encoding = conn.execute(
                            "SELECT current_user,current_database(),current_setting('timezone'),current_setting('server_encoding')"
                        ).fetchone()
                        self.assertEqual(
                            (user, database, tz, encoding),
                            (init.DATABASES[dbname], dbname, "UTC", "UTF8"),
                        )
                for i, dsn in enumerate(strings):
                    params = conninfo_to_dict(dsn)
                    params["dbname"] = conninfo_to_dict(
                        strings[(i + 1) % len(strings)]
                    )["dbname"]
                    with self.assertRaises(psycopg.OperationalError):
                        psycopg.connect(**params)
                self.assertEqual(
                    dotenv_values(runtime / "lab.env")[
                        "FORECAST_LAB_SCHEDULER_ENABLED"
                    ],
                    "0",
                )
            finally:
                subprocess.run(
                    [
                        bindir / "pg_ctl.exe",
                        "-D",
                        runtime / "pgdata",
                        "stop",
                        "-m",
                        "fast",
                        "-w",
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                )
