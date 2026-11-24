"""Read-only HTTP contract and full worker cycle in an ephemeral schema on the acceptance DB."""

import os
import tempfile
import unittest
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import exchange_calendars
import psycopg
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from tradingagents.forecast_lab.app import application
from tradingagents.forecast_lab.engine import ForecastUnavailable
from tradingagents.forecast_lab.incumbent import IncumbentCollector
from tradingagents.forecast_lab.store import Store
from tradingagents.forecast_lab.worker import Progress, Worker, reason


class WorkerRecoveryTest(unittest.TestCase):
    def test_only_known_engine_reasons_are_displayed(self):
        corporate_action = "Latest 21-session prices incomplete or crossed an uncertain corporate action"
        for text in (corporate_action, "Entry session has already opened",
                     "Fewer than 20 complete historical five-session windows",
                     "Instrument classification or listing exchange changed"):
            with self.subTest(text=text):
                self.assertEqual(reason(ForecastUnavailable(text)), text)
        url = "https://vendor.invalid/data?token=private"
        self.assertEqual(reason(ForecastUnavailable(f"{corporate_action}: {url}")), "ForecastUnavailable")
        self.assertEqual(reason(ConnectionError(url)), "ConnectionError")

    def test_rotation_progress_survives_crash_and_single_symbol_failure(self):
        store = Mock()
        store.worker_lock.side_effect = lambda: nullcontext(True)
        store.pending_cases.return_value = []
        store.list_tickers.return_value = [
            {"ticker": "ZZZ", "market": "us"},
            {"ticker": "AAA", "market": "us"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            first = Worker(store, Mock(), Progress(tmp))
            with patch.object(first, "issue", side_effect=ConnectionError("fixture")):
                failed = first.scan(limit=1)
            self.assertEqual(failed["cursor"], "AAA")
            self.assertEqual(failed["failures"], {"AAA": "ConnectionError"})
            restarted = Worker(store, Mock(), Progress(tmp))
            with patch.object(restarted, "issue", return_value=10) as issued:
                self.assertEqual(restarted.scan(limit=1)["cursor"], "ZZZ")
            self.assertEqual(issued.call_args.args[0]["ticker"], "ZZZ")

    def test_failed_arm_retries_are_bounded(self):
        clock = datetime(2026, 3, 2, 22, tzinfo=UTC)
        store, engine = Mock(), Mock()
        case = {
            "id": 1,
            "snapshot": {"entry_open_at": (clock + timedelta(hours=1)).isoformat()},
            "arms": [
                {"method": method, "status": "published", "audit": {}}
                for method in ("single", "memory", "baseline")
            ],
        }
        case["arms"].append(
            {"method": "debate", "status": "failed", "audit": {"attempts": 3}}
        )
        with tempfile.TemporaryDirectory() as tmp:
            Worker(store, engine, Progress(tmp), clock=lambda: clock).issue_frozen(
                case, {}
            )
        engine.forecast.assert_not_called()


class ClockConnection(psycopg.Connection):
    def execute(self, query, *args, **kwargs):
        if isinstance(query, str):
            for func in ("clock_timestamp()", "statement_timestamp()"):
                query = query.replace(
                    func, "current_setting('forecast_lab.test_now')::timestamptz"
                )
        return super().execute(query, *args, **kwargs)


class FixtureStore(Store):
    def _connect(self):
        stamp = self.clock().isoformat()
        return ClockConnection.connect(
            self._dsn,
            row_factory=dict_row,
            options=(
                f"-c search_path={self.schema},pg_catalog -c forecast_lab.test_now={stamp} -c timezone=UTC"
            ),
        )


class FixtureEngine:
    def __init__(self, clock):
        self.clock = clock
        self.fail_once = True
        self.snapshots = 0

    def snapshot(self, ticker, market):
        self.snapshots += 1
        cal = exchange_calendars.get_calendar("XNYS")
        day = self.clock().date()
        days = cal.sessions_in_range(day + timedelta(days=1), day + timedelta(days=20))[
            :5
        ]
        return {
            "ticker": ticker,
            "market": market,
            "data_session": day.isoformat(),
            "observed_at": self.clock().isoformat(),
            "experiment_version": "fixture-only",
            "sessions": [x.date().isoformat() for x in days],
            "entry_open_at": cal.session_open(days[0]).isoformat(),
            "exit_close_at": cal.session_close(days[-1]).isoformat(),
            "features": {"change": 0.1},
            "bars": [
                {
                    "date": day.isoformat(),
                    "low": 99,
                    "open": 100,
                    "close": 100,
                    "high": 102,
                    "volume": 100,
                    "split": 0,
                }
            ],
            "source": "fixture",
        }

    def forecast(self, snap, method, memory=None):
        if self.fail_once and method == "single":
            self.fail_once = False
            raise RuntimeError("fixture model unavailable")
        return {
            "method": method,
            "probability": 0.8 if method == "memory" else 0.5,
            "model": "fixture",
            "version": "fixed-v1",
            "rationale": "fixed evidence",
            "memory_id": memory["id"] if memory else None,
        }

    def outcome(self, snap):
        if self.clock() < datetime.fromisoformat(snap["exit_close_at"]):
            return None
        return {
            "status": "scored",
            "entry_open": 100,
            "exit_close": 102,
            "actual": 1,
            "source": "fixture",
            "observed_at": self.clock().isoformat(),
            "evidence": {
                "sessions": snap["sessions"],
                "bars": [
                    {
                        "date": d,
                        "open": 100,
                        "high": 103,
                        "low": 99,
                        "close": 102,
                        "volume": 100,
                        "split": 0,
                    }
                    for d in snap["sessions"]
                ],
            },
        }


class LabAcceptanceTest(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("FORECAST_LAB_ACCEPTANCE_DSN"), "isolated acceptance DB required"
    )
    def test_forecast_maturity_memory_feedback_and_dashboard(self):
        dsn = os.environ["FORECAST_LAB_ACCEPTANCE_DSN"]
        params = conninfo_to_dict(dsn)
        self.assertEqual(
            (params["host"], params["port"], params["dbname"]),
            ("127.0.0.1", "55434", "forecast_lab_acceptance"),
        )
        namespace = "qa_worker_" + uuid.uuid4().hex
        with psycopg.connect(dsn) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(namespace)))

        def cleanup():
            with psycopg.connect(dsn) as conn:
                conn.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(namespace))
                )

        self.addCleanup(cleanup)
        store = FixtureStore(dsn)
        store.schema = namespace
        clock = [datetime(2026, 3, 2, 22, tzinfo=UTC)]
        store.clock = lambda: clock[0]
        engine = FixtureEngine(store.clock)
        with tempfile.TemporaryDirectory() as tmp:
            progress = Progress(Path(tmp))

            def public_reports(ticker):
                stamp = clock[0].isoformat()
                return [
                    {
                        "id": clock[0].date().toordinal(),
                        "ticker": ticker,
                        "created_at": stamp,
                        "pipeline_strategy": {
                            "forecast_5s": {
                                "p_up": 0.6,
                                "judge_model": "observed fixture",
                                "market_data_date": str(clock[0].date()),
                            }
                        },
                    }
                ]

            collector = IncumbentCollector(store, public_reports, store.clock)
            worker = Worker(store, engine, progress, clock=store.clock)
            with TestClient(
                application(store, worker, progress, enabled=False)
            ) as http:
                self.assertTrue(http.get("/ready").json()["ready"])
                store.set_ticker("SPY", "us")
                watch = http.get("/api/status").json()["tickers"]
                self.assertEqual(watch, [{
                    "ticker": "SPY", "market": "us",
                    "classification": {
                        "version": "research-2026-11-24", "asset_class": "etf",
                        "sector": None, "industry": None, "exposure": "us_large_cap",
                    },
                }])
                worker.scan()
                first = http.get("/api/cases").json()[0]
                first_id = first["id"]
                path = f"/api/cases/{first_id}"
                first_detail = http.get(path)
                tag = first_detail.headers["etag"]
                unchanged = http.get(path, headers={"If-None-Match": tag})
                self.assertEqual((unchanged.status_code, unchanged.content), (304, b""))
                self.assertIsNone(first_detail.json()["reference"])
                worker.reference = collector
                self.assertEqual(worker.capture(), 1)
                referenced = http.get(path, headers={"If-None-Match": tag})
                self.assertEqual(referenced.status_code, 200)
                self.assertIsNotNone(referenced.json()["reference"])
                tag = referenced.headers["etag"]
                # The entry deadline changes a pending case without any row rewrite.
                original_now = clock[0]
                clock[0] = datetime.fromisoformat(first["entry_open_at"])
                at_open = http.get(path, headers={"If-None-Match": tag})
                self.assertEqual(at_open.status_code, 200)
                self.assertEqual(at_open.json()["status"], "awaiting")
                clock[0] = original_now
                arms = first_detail.json()["arms"]
                self.assertEqual(
                    {r["method"]: r["status"] for r in arms},
                    {
                        "single": "failed",
                        "baseline": "published",
                        "debate": "published",
                        "memory": "skipped",
                    },
                )
                with store.worker_lock() as got:
                    self.assertTrue(got)
                    self.assertEqual(worker.scan(), {"phase": "busy"})
                restarted = Worker(
                    store, engine, Progress(tmp), clock=store.clock, reference=collector
                )
                restarted.scan()
                self.assertEqual(engine.snapshots, 1)
                updated = http.get(path, headers={"If-None-Match": tag})
                self.assertEqual(updated.status_code, 200)
                self.assertNotEqual(updated.headers["etag"], tag)
                self.assertEqual(updated.json()["status"], "awaiting")
                clock[0] = datetime(2026, 3, 9, 22, tzinfo=UTC)
                restarted.scan(limit=0)
                matured = http.get(path, headers={"If-None-Match": updated.headers["etag"]})
                self.assertEqual(matured.status_code, 200)
                self.assertEqual(matured.json()["status"], "matured")
                self.assertTrue(matured.json()["memory"])
                clock[0] += timedelta(minutes=1)
                restarted.scan()
                second = http.get("/api/cases").json()[0]
                second_detail = http.get(f"/api/cases/{second['id']}").json()
                self.assertEqual(second_detail["selected_memory"]["case_id"], first_id)
                self.assertEqual(
                    next(a for a in second_detail["arms"] if a["method"] == "memory")[
                        "probability"
                    ],
                    0.8,
                )
                clock[0] = datetime(2026, 3, 16, 22, tzinfo=UTC)
                restarted.scan(limit=0)
                restarted.scan(limit=0)
                results = http.get("/api/stats").json()
                pair = next(
                    c
                    for c in results["comparisons"]
                    if (c["control"], c["treated"]) == ("single", "memory")
                )
                ref = next(
                    r
                    for r in results["reference_comparisons"]
                    if r["method"] == "single"
                )
                self.assertEqual(ref["n"], 2)
                self.assertAlmostEqual(ref["source_brier"], 0.16)
                self.assertEqual(pair["n"], 1)
                self.assertAlmostEqual(pair["improvement"], 0.21)
                archive = http.get(
                    "/api/cases",
                    params={"limit": 1, "before_id": second["id"], "market": "us"},
                ).json()
                self.assertEqual([item["id"] for item in archive], [first_id])
                cohort = http.get(
                    "/api/stats",
                    params={
                        "market": "us",
                        "from_date": "2026-03-09",
                        "to_date": "2026-03-09",
                    },
                ).json()
                self.assertEqual(cohort["counts"]["matured"], 1)
                self.assertEqual(http.get("/api/stats?market=invalid").status_code, 422)
                self.assertEqual(
                    http.get(
                        "/api/cases?from_date=2026-03-09&to_date=2026-03-02"
                    ).status_code,
                    422,
                )
                self.assertEqual(results["counts"]["matured"], 2)
                self.assertEqual(
                    http.get("/api/status").json()["progress"]["phase"], "idle"
                )
                self.assertEqual(http.get("/api/cases/9999999").status_code, 404)
                self.assertEqual(http.post("/api/cases").status_code, 405)
                self.assertIn("시장 예측 연구실", http.get("/").text)
