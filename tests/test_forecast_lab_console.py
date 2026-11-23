"""Verify the shared-origin console against a private, short-lived PostgreSQL cluster."""

import os
import secrets
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import psycopg
from fastapi.testclient import TestClient
from tradingagents.forecast_lab.console import checked_dsn


class ConsoleIsolationTests(unittest.TestCase):
    def test_refuses_wrong_database_role_host_and_indirect_connections(self):
        base = "host=127.0.0.1 port=55434 dbname=forecast_lab_console user=forecast_lab_console_app password=fake"
        for bad in (
            base.replace("55434", "5432"),
            base.replace("127.0.0.1", "example.org"),
            base.replace("dbname=forecast_lab_console", "dbname=forecast_lab_research"),
            base.replace("user=forecast_lab_console_app", "user=postgres"),
            base + " options=-c",
            base + " service=production",
            base + " hostaddr=127.0.0.2",
            "invalid",
        ):
            with self.subTest(), self.assertRaises(ValueError):
                checked_dsn(bad, "forecast_lab_console", "forecast_lab_console_app")

    @unittest.skipUnless(
        os.getenv("PG_TEST_BINDIR"), "requires private native PostgreSQL binaries"
    )
    def test_full_api_mount_uses_private_cluster_and_own_lifespan(self):
        pg = Path(os.environ["PG_TEST_BINDIR"])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            password = secrets.token_hex(24)
            pwfile = root / "pass"
            pwfile.write_text(password, encoding="ascii")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            role = "forecast_lab_console_app"
            subprocess.run(
                [
                    pg / "initdb",
                    "-D",
                    root / "pg",
                    "-U",
                    role,
                    "--auth=scram-sha-256",
                    "--pwfile",
                    pwfile,
                    "--locale=C",
                    "--encoding=UTF8",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            subprocess.run(
                [
                    pg / "pg_ctl",
                    "-D",
                    root / "pg",
                    "-l",
                    root / "postgres.log",
                    "-o",
                    f"-p {port} -h 127.0.0.1",
                    "start",
                    "-w",
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )
            try:
                base = f"postgresql://{role}:{password}@127.0.0.1:{port}/"
                with psycopg.connect(base + "postgres", autocommit=True) as conn:
                    conn.execute("CREATE DATABASE forecast_lab_console")
                header = f"postgresql://{role}:{password}@127.0.0.1:55434/"
                (root / "console.env").write_text(
                    "FORECAST_LAB_CONSOLE_DSN=" + header + "forecast_lab_console\n"
                    "TRADINGAGENTS_ADMIN_TOKEN=fixture-token\n",
                    encoding="ascii",
                )
                (root / "lab.env").write_text(
                    "FORECAST_LAB_DSN=" + header + "forecast_lab_research\n",
                    encoding="ascii",
                )
                subprocess.run(
                    [sys.executable, __file__],
                    check=True,
                    timeout=150,
                    env={
                        **os.environ,
                        "CONSOLE_TEST_ROOT": temp,
                        "CONSOLE_TEST_PORT": str(port),
                        "DATABASE_URL": "invalid-production-source",
                        "SUPABASE_DB_URL": "invalid-production-source",
                        "SUPABASE_DIRECT_URL": "invalid-production-source",
                        "TRADINGAGENTS_ADMIN_TOKEN": "wrong",
                    },
                )
                with psycopg.connect(base + "forecast_lab_console") as conn:
                    self.assertEqual(
                        conn.execute(
                            "SELECT status,initial_capital FROM portfolio_configs"
                        ).fetchall(),
                        [("active", 2500)],
                    )
            finally:
                subprocess.run(
                    [pg / "pg_ctl", "-D", root / "pg", "stop", "-m", "fast", "-w"],
                    check=True,
                    stdout=subprocess.DEVNULL,
                )


def fixture():
    from tradingagents.forecast_lab.app import application
    from tradingagents.forecast_lab.console import configure_runtime, console_ready
    from tradingagents.forecast_lab.worker import Progress

    root = Path(os.environ["CONSOLE_TEST_ROOT"])
    port = int(os.environ["CONSOLE_TEST_PORT"])
    assert port != 55434
    original_connect = psycopg.connect

    def private_connect(dsn, *args, **kwargs):
        if dsn != os.environ["TRADINGAGENTS_DB_URL"]:
            raise AssertionError("unexpected database configuration")
        return original_connect(dsn.replace(":55434/", f":{port}/"), *args, **kwargs)

    with patch.object(psycopg, "connect", side_effect=private_connect):
        console = configure_runtime(root, root / "lab.env")
        from tradingagents.api import app as original
        from tradingagents.default_config import DEFAULT_CONFIG

        assert Path.cwd() == root / "console"
        assert Path(DEFAULT_CONFIG["data_cache_dir"]).is_relative_to(root / "console")
        assert Path(DEFAULT_CONFIG["chroma_path"]).is_relative_to(root / "console")
        assert (
            not os.getenv("SUPABASE_DB_URL")
            and not os.getenv("SUPABASE_DIRECT_URL")
            and not os.getenv("DATABASE_URL")
        )
        dist = root / "dist"
        dist.mkdir()
        (dist / "index.html").write_text("workspace fixture", encoding="utf8")
        (dist / "assets").mkdir()
        (dist / "assets" / "app.js").write_text("fake bundle", encoding="utf8")
        research = Mock()
        research.list_tickers.return_value = []
        ready = Mock(side_effect=console_ready)
        app = application(
            research,
            Mock(),
            Progress(root),
            enabled=False,
            console=console,
            dist=dist,
            readiness=ready,
        )
        with TestClient(app) as client:
            assert client.get("/").text == "workspace fixture"
            assert client.get("/assets/app.js").text == "fake bundle"
            assert client.get("/research/").status_code == 200
            assert client.get("/lab.js").status_code == 200
            assert client.get("/api/status").status_code == 200
            assert client.get("/workspace-api/health").json()["scheduler_running"]
            assert client.get("/ready").json() == {"ready": True, "console": True}
            ready.side_effect = None
            ready.return_value = False
            assert client.get("/ready").status_code == 503
            assert client.get("/health").status_code == 200
            endpoint = "/workspace-api/portfolio/config"
            assert client.get(endpoint).json()["config"] is None
            body = {"initial_capital": 2500, "base_currency": "USD"}
            assert client.post(endpoint, json=body).status_code in (401, 403)
            assert (
                client.post(
                    endpoint, json=body, headers={"Authorization": "Bearer wrong"}
                ).status_code
                == 401
            )
            auth = {"Authorization": "Bearer fixture-token"}
            assert (
                client.post(endpoint, json=body, headers=auth).json()["config"][
                    "status"
                ]
                == "active"
            )
            for action, status in (("pause", "paused"), ("resume", "active")):
                assert (
                    client.post(endpoint + "/" + action, headers=auth).status_code
                    == 200
                )
                assert client.get(endpoint).json()["config"]["status"] == status
            with client.websocket_connect("/workspace-api/ws/analyze/FIXTURE") as ws:
                assert ws.receive_json()["status"] == "waiting"
            queue = original.queue_worker_task
            assert not queue.done()
        assert queue.cancelled() and not original.scheduler.is_running()


if __name__ == "__main__":
    if os.environ.get("CONSOLE_TEST_ROOT"):
        fixture()
    else:
        unittest.main()
