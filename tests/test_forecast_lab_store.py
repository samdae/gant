"""Private PostgreSQL acceptance for the prospective laboratory, with explicit historical fixtures."""

import os
import secrets
import socket
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import exchange_calendars
import psycopg
from psycopg.types.json import Jsonb
from tradingagents.forecast_lab.store import Store


class IsolationTests(unittest.TestCase):
    def test_rejects_other_database_and_implicit_or_remote_connection(self):
        for dsn in (
            "",
            "dbname=postgres host=127.0.0.1 user=test port=5432",
            "dbname=forecast_lab_test host=example.com user=test port=55434",
            "dbname=forecast_lab_test host=127.0.0.1 hostaddr=192.0.2.1 user=test port=55434",
        ):
            with self.assertRaises(ValueError):
                Store(dsn)


@unittest.skipUnless(
    os.environ.get("PG_TEST_BINDIR"), "requires private PostgreSQL binaries"
)
class ForecastStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temp.cleanup)
        pg = Path(os.environ["PG_TEST_BINDIR"])
        data = Path(temp.name) / "pgdata"
        password = secrets.token_hex(24)
        pwfile = Path(temp.name) / "password"
        pwfile.write_text(password, encoding="ascii")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        subprocess.run(
            [
                pg / "initdb",
                "-D",
                data,
                "-U",
                "test",
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
                data,
                "-l",
                Path(temp.name) / "postgres.log",
                "-o",
                f"-p {port} -h 127.0.0.1",
                "start",
                "-w",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        cls.addClassCleanup(
            subprocess.run,
            [pg / "pg_ctl", "-D", data, "stop", "-m", "fast", "-w"],
            check=True,
        )
        base = f"postgresql://test:{password}@127.0.0.1:{port}/"
        with psycopg.connect(base + "postgres", autocommit=True) as conn:
            conn.execute("CREATE DATABASE forecast_lab_test")
        cls.store = Store(base + "forecast_lab_test")
        cls.store.init()

    def setUp(self):
        with self.store._connect() as conn:
            conn.execute("TRUNCATE lab_cases,lab_watchlist RESTART IDENTITY CASCADE")

    def snapshot(self, ticker="FIX", days_ago=0):
        now = datetime.now(UTC) - timedelta(days=days_ago)
        for market, name in (("us", "XNYS"), ("kr", "XKRX")):
            cal = exchange_calendars.get_calendar(name)
            dates = cal.sessions_in_range(
                now.date() - timedelta(days=15), now.date() + timedelta(days=25)
            )
            i = max(
                i
                for i, s in enumerate(dates)
                if cal.session_close(s) + timedelta(minutes=20) <= now
            )
            if now >= cal.session_open(dates[i + 1]):
                continue
            window = dates[i + 1 : i + 6]
            return {
                "ticker": ticker,
                "market": market,
                "experiment_version": "fixture-v1",
                "data_session": dates[i].date().isoformat(),
                "entry_open_at": cal.session_open(window[0]).isoformat(),
                "observed_at": now.isoformat(),
                "exit_close_at": cal.session_close(window[-1]).isoformat(),
                "sessions": [s.date().isoformat() for s in window],
                "features": {"trend_20d": 0.1},
                "source": "fixture",
                "bars": [
                    {
                        "date": dates[i].date().isoformat(),
                        "open": 100,
                        "close": 100,
                        "low": 99,
                        "high": 101,
                        "volume": 50,
                        "split": 0,
                    }
                ],
            }
        self.fail("no prospective market")

    def historical(self, ticker, days_ago, methods):
        # This simulates an already-published record ONLY inside this fresh private test cluster.
        snap = self.snapshot(ticker, days_ago)
        with self.store._connect() as conn:
            cid = conn.execute(
                """INSERT INTO lab_cases(ticker,market,data_session,experiment_version,snapshot,
                observed_at,entry_at,exit_at,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                (
                    ticker,
                    snap["market"],
                    snap["data_session"],
                    snap["experiment_version"],
                    Jsonb(snap),
                    snap["observed_at"],
                    snap["entry_open_at"],
                    snap["exit_close_at"],
                    snap["observed_at"],
                ),
            ).fetchone()["id"]
            for method, p, version, mid in methods:
                conn.execute(
                    """INSERT INTO lab_arms(case_id,method,status,probability,rationale,model,version,
                    memory_id,audit,published_at) VALUES(%s,%s,'published',%s,'fixture','fixed-model',%s,%s,'{}',%s)""",
                    (cid, method, p, version, mid, snap["observed_at"]),
                )
        return cid, snap

    def settle(self, cid, snap):
        days = snap["sessions"]
        evidence = {
            "observed_at": datetime.now(UTC).isoformat(),
            "source": "fixture",
            "evidence": {
                "sessions": days,
                "bars": [
                    {
                        "date": d,
                        "open": 100,
                        "close": 110,
                        "low": 95,
                        "high": 115,
                        "volume": 50,
                        "split": 0,
                    }
                    for d in days
                ],
            },
        }
        return self.store.record_outcome(
            cid, entry_open=100, exit_close=110, evidence=evidence
        )

    def test_concurrent_idempotency_deadlines_and_lock(self):
        s = self.store
        snap = self.snapshot()
        with ThreadPoolExecutor(2) as pool:
            ids = list(pool.map(s.create_case, [snap, snap]))
        self.assertEqual(ids[0], ids[1])
        cid = ids[0]
        self.assertTrue(s.record_arm(cid, "single", status="failed", error="transient"))

        def publish(_):
            return s.record_arm(
                cid,
                "single",
                probability=0.25,
                rationale="record",
                model="fixed",
                version="v1",
            )

        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(publish, range(2))), [False, True])
        with self.assertRaises(ValueError):
            s.record_arm(
                cid,
                "debate",
                probability=1.0001,
                model="m",
                version="v",
                rationale="out of range",
            )
        self.assertFalse(self.settle(cid, snap))
        self.assertIsNone(s.select_memory(cid))
        with s.worker_lock() as first, s.worker_lock() as second:
            self.assertTrue(first)
            self.assertFalse(second)
        with s.worker_lock() as next_run:
            self.assertTrue(next_run)
        self.assertEqual(s.detail(cid)["arms"][0]["probability"], 0.25)
        with self.assertRaises(ValueError):
            s.create_case({**snap, "exit_close_at": snap["entry_open_at"]})
        with self.assertRaises(ValueError):
            s.create_case({**snap, "bars": [{"date": snap["sessions"][0]}]})
        with self.assertRaises(ValueError):
            s.create_case(self.snapshot("OLD", 20))

    def test_maturity_cutoff_matched_brier_and_paper_return(self):
        s = self.store
        source, snap = self.historical("FIX", 35, [("single", 0.2, "v1", None)])
        early = self.snapshot("EARLY")
        early_id = s.create_case(early)
        self.assertTrue(self.settle(source, snap))
        self.assertFalse(self.settle(source, snap))
        self.assertFalse(
            s.record_arm(
                source,
                "baseline",
                probability=0.1,
                model="m",
                version="v",
                rationale="late",
            )
        )
        self.assertIsNone(s.select_memory(early_id))
        # Market choice for synthetic prior sessions may differ across time zones.
        current = self.snapshot()
        if current["market"] != snap["market"]:
            with s._connect() as conn:
                conn.execute(
                    "UPDATE lab_cases SET market=%s WHERE id=%s",
                    (current["market"], source),
                )
        target = s.create_case(current)
        memory = s.select_memory(target)
        self.assertEqual(memory["case_id"], source)
        self.assertTrue(
            s.record_arm(
                target,
                "memory",
                memory_id=memory["id"],
                probability=0.9,
                model="fixed",
                version="v1",
                rationale="lesson",
            )
        )
        paired, ps = self.historical(
            "PAIRED",
            14,
            [("single", 0.5, "v1", None), ("memory", 0.9, "v1", memory["id"])],
        )
        self.assertTrue(self.settle(paired, ps))
        skew, ss = self.historical(
            "SKEW",
            14,
            [("single", 0.99, "v2", None), ("memory", 0.05, "v1", memory["id"])],
        )
        self.assertTrue(self.settle(skew, ss))
        (pair,) = s.stats()["comparisons"]
        self.assertEqual(pair["n"], 1)
        self.assertAlmostEqual(pair["improvement"], 0.24)
        self.assertAlmostEqual(pair["control_paper_return"], 0)
        self.assertAlmostEqual(pair["paper_improvement"], 0.1)
        self.assertEqual(s.stats()["memory_effects"][0]["n"], 1)
        self.assertEqual(s.detail(paired)["selected_memory"]["id"], memory["id"])

    def test_learning_uses_only_pre_cutoff_nonoverlapping_matched_evidence(self):
        s = self.store
        # Known mature prior lessons in the isolated replay, older and newer.
        memories = []
        current = self.snapshot("SOURCE")
        for days in (84, 70):
            cid, snap = self.historical("SOURCE", days, [("single", 0.4, "v1", None)])
            self.settle(cid, snap)
            mid = s.detail(cid)["memory"]["id"]
            with s._connect() as conn:
                conn.execute(
                    "UPDATE lab_cases SET market=%s WHERE id=%s",
                    (current["market"], cid),
                )
                conn.execute(
                    "UPDATE lab_outcomes SET observed_at=%s WHERE case_id=%s",
                    (snap["exit_close_at"], cid),
                )
                conn.execute(
                    "UPDATE lab_memories SET created_at=%s WHERE id=%s",
                    (snap["exit_close_at"], mid),
                )
            memories.append(mid)
        a, b = memories
        old, _ = self.historical("SOURCE", 9, [("single", 0.5, "v1", None)])
        with s._connect() as conn:
            conn.execute(
                "UPDATE lab_cases SET market=%s WHERE id=%s", (current["market"], old)
            )
        self.assertEqual(s.select_memory(old)["id"], b)
        # Two strongly overlapping positive target windows for a; one negative for b.
        pairs = []
        for ticker, days, mid, p in (
            ("TREAT", 35, a, 0.9),
            ("TREAT", 28, a, 0.9),
            ("OTHER", 21, b, 0.1),
        ):
            cid, snap = self.historical(
                ticker, days, [("single", 0.5, "v1", None), ("memory", p, "v1", mid)]
            )
            self.settle(cid, snap)
            pairs.append(cid)
        with s._connect() as conn:
            conn.execute(
                """UPDATE lab_cases c SET exit_at=other.exit_at FROM lab_cases other
                WHERE c.id=%s AND other.id=%s""",
                (pairs[0], pairs[1]),
            )
        # Looking up the old target after those evaluations still returns the exact neutral prior.
        self.assertEqual(s.select_memory(old)["id"], b)
        self.assertEqual(s.select_memory(old)["uplift_support"], 0)
        current = self.snapshot("SOURCE")
        live = s.create_case(current)
        s.record_arm(
            live,
            "single",
            probability=0.5,
            rationale="control",
            model="fixed-model",
            version="v1",
        )
        selected = s.select_memory(live)
        self.assertEqual(selected["id"], a)
        self.assertEqual(selected["uplift_support"], 1)
        self.assertAlmostEqual(selected["shrunk_uplift"], 0.24 / 6)
        s.record_arm(
            live,
            "memory",
            probability=0.7,
            rationale="applied",
            model="fixed-model",
            version="v1",
            memory_id=a,
        )
        self.assertAlmostEqual(
            s.detail(live)["selected_memory"]["shrunk_uplift"], 0.24 / 6
        )
        self.assertGreater(len(s.stats()["calibration"]), 0)
        for row in s.stats()["comparisons"]:
            self.assertGreater(row["distinct_entry_dates"], 0)
            self.assertGreater(row["distinct_tickers"], 0)

    def test_sector_migration_preserves_legacy_rows_and_custom_constraints(self):
        s = self.store
        case = s.create_case(self.snapshot())
        before = s.detail(case)
        with s._connect() as conn:
            conn.execute("""ALTER TABLE lab_arms DROP CONSTRAINT lab_arms_method_sector_v1,
                DROP CONSTRAINT lab_arms_citation_sector_v1,
                ADD CONSTRAINT backup_custom_methods CHECK(method IN ('baseline','single','debate','memory')),
                ADD CONSTRAINT backup_custom_memory CHECK(memory_id IS NULL OR method='memory'),
                ADD CONSTRAINT backup_operator_check CHECK(method<>'other-method')""")
        try:
            s.init()
            s.init()
            self.assertEqual(before, s.detail(case))
            with s._connect() as conn:
                names = {
                    r["conname"]
                    for r in conn.execute(
                        "SELECT conname FROM pg_constraint WHERE conrelid='lab_arms'::regclass"
                    )
                }
            self.assertIn("backup_operator_check", names)
            self.assertNotIn("backup_custom_methods", names)
            self.assertNotIn("backup_custom_memory", names)
        finally:
            with s._connect() as conn:
                conn.execute(
                    "ALTER TABLE lab_arms DROP CONSTRAINT IF EXISTS backup_operator_check"
                )

    def test_sector_policy_publication_guards_coverage_and_distinct_scoring(self):
        from test_forecast_lab_sector_retrieval import group, features

        s = self.store
        target_snap = self.snapshot("GEV")
        target_snap.update(
            retrieval_policy="sector-v1", classification=group(), features=features()
        )

        def prior(ticker, days, trend, mature):
            cid, snap = self.historical(
                ticker,
                days,
                [("single" if mature is True else "baseline", 0.5, "v1", None)]
                if mature
                else [],
            )
            if mature:
                self.settle(cid, snap)
            snap.update(
                retrieval_policy="sector-v1",
                classification=group(),
                features=features(trend),
            )
            with s._connect() as conn:
                conn.execute(
                    "UPDATE lab_cases SET snapshot=%s,market=%s WHERE id=%s",
                    (Jsonb(snap), target_snap["market"], cid),
                )
                if mature:
                    conn.execute(
                        "UPDATE lab_outcomes SET observed_at=%s WHERE case_id=%s",
                        (snap["exit_close_at"], cid),
                    )
                    conn.execute(
                        "UPDATE lab_memories SET created_at=%s WHERE case_id=%s",
                        (snap["exit_close_at"], cid),
                    )
            return cid

        old = prior("GEV", 84, 0.148, True)
        other = prior("ETN", 70, 0.062, True)
        live = s.create_case(target_snap)
        arm = dict(
            model="fixed-model",
            version="v1",
            rationale="fixture",
            probability=0.6,
            audit={"market_input_sha256": "f" * 64},
        )
        s.record_arm(live, "single", **arm)
        ctrl = s.select_memory(live)["id"]
        self.assertEqual(s.select_memory(live, "memory_sector")["id"], ctrl)
        w = prior("GEV", 70, 0.060, "witness")
        selected = s.select_memory(live, "memory_sector")
        self.assertEqual(
            (selected["case_id"], selected["sector_selection_v1"]["peer_case_id"]),
            (other, w),
        )
        self.assertEqual(selected["uplift_support"], 0)
        # Snapshots first captured after target publication cannot corroborate the past case.
        with s._connect() as conn:
            clocks = conn.execute(
                "SELECT created_at, entry_at, exit_at FROM lab_cases WHERE id=%s", (w,)
            ).fetchone()
            conn.execute(
                """UPDATE lab_cases SET created_at=clock_timestamp(),entry_at=clock_timestamp()+interval '1 day',
                exit_at=clock_timestamp()+interval '10 days' WHERE id=%s""",
                (w,),
            )
        self.assertEqual(s.select_memory(live, "memory_sector")["id"], ctrl)
        with s._connect() as conn:
            conn.execute(
                "UPDATE lab_cases SET created_at=%s,entry_at=%s,exit_at=%s WHERE id=%s",
                (clocks["created_at"], clocks["entry_at"], clocks["exit_at"], w),
            )
        with s._connect() as conn:
            conn.execute(
                "UPDATE lab_outcomes SET observed_at=clock_timestamp() WHERE case_id=%s",
                (w,),
            )
        self.assertEqual(s.select_memory(live, "memory_sector")["id"], ctrl)
        with s._connect() as conn:
            conn.execute(
                "UPDATE lab_outcomes SET observed_at=%s WHERE case_id=%s",
                (clocks["exit_at"], w),
            )
        with self.assertRaises(ValueError):
            s.record_arm(live, "memory_sector", memory_id=selected["id"], **arm)
        s.record_arm(live, "memory", memory_id=ctrl, **arm)
        with self.assertRaises(ValueError):
            s.record_arm(live, "memory_sector", status="skipped", error="same_memory")
        with self.assertRaises(ValueError):
            s.record_arm(live, "memory_sector", memory_id=ctrl, **arm)
        for method in ("baseline", "debate"):
            s.record_arm(live, method, **arm)
        self.assertEqual(s.detail(live)["status"], "pending")
        self.assertTrue(
            s.record_arm(
                live,
                "memory_sector",
                memory_id=selected["id"],
                **{**arm, "probability": 0.8},
            )
        )
        detail = s.detail(live)
        self.assertEqual(detail["status"], "awaiting")
        self.assertEqual(set(detail["selected_memories"]), {"memory", "memory_sector"})
        self.assertEqual(detail["selected_memory"]["case_id"], old)
        diag = detail["selected_memories"]["memory_sector"]
        self.assertEqual(
            (diag["control_memory_id"], diag["peer_reference"]),
            (ctrl, "market_benchmark"),
        )
        # The following outcome is a private, controlled clock replay.
        with s._connect() as conn:
            conn.execute(
                """INSERT INTO lab_outcomes(case_id,status,entry_open,exit_close,actual,observed_at,evidence)
                VALUES(%s,'scored',100,110,1,clock_timestamp(),'{}')""",
                (live,),
            )
        stats = s.stats(
            target_snap["market"],
            target_snap["data_session"],
            target_snap["data_session"],
        )
        self.assertEqual(stats["sector_coverage"]["scored"], 1)
        (basis,) = stats["sector_by_basis"]
        self.assertEqual((basis["basis"], basis["n"]), ("equity_peer", 1))
        self.assertAlmostEqual(basis["improvement"], 0.12)
        self.assertEqual(
            s.stats(from_date="2099-01-01")["sector_coverage"]["eligible_cases"], 0
        )
        for column, value in (
            ("model", "different"),
            ("version", "different"),
            ("audit", Jsonb({"market_input_sha256": "different"})),
            ("memory_id", ctrl),
        ):
            with s._connect() as conn:
                conn.execute(
                    f"UPDATE lab_arms SET {column}=%s WHERE case_id=%s AND method='memory_sector'",
                    (value, live),
                )
            self.assertEqual(s.stats()["sector_coverage"]["scored"], 0)
            with s._connect() as conn:
                original = {
                    "model": arm["model"],
                    "version": arm["version"],
                    "audit": Jsonb(arm["audit"]),
                    "memory_id": selected["id"],
                }[column]
                conn.execute(
                    f"UPDATE lab_arms SET {column}=%s WHERE case_id=%s AND method='memory_sector'",
                    (original, live),
                )
        unknown_snap = self.snapshot("UNKNOWN")
        unknown_snap.update(
            retrieval_policy="sector-v1",
            classification=group(None, None, "unknown"),
            features=features(),
        )
        unknown = s.create_case(unknown_snap)
        self.assertIsNone(s.select_memory(unknown, "memory_sector"))
        self.assertTrue(
            s.record_arm(
                unknown,
                "memory_sector",
                status="skipped",
                error="no_eligible_sector_memory",
            )
        )
        legacy = s.create_case(self.snapshot("LEGACY"))
        with self.assertRaises(ValueError):
            s.record_arm(legacy, "memory_sector", status="failed", error="failure")
        self.assertIsNone(s.select_memory(legacy, "memory_sector"))
        self.assertTrue(s.init() is None)

    def test_sector_only_use_changes_future_policy_ranking_not_legacy_control(self):
        from test_forecast_lab_sector_retrieval import group, features

        s = self.store
        target = self.snapshot("X")
        target.update(
            retrieval_policy="sector-v1", classification=group(), features=features()
        )

        def historic(ticker, days, methods, mature=True):
            cid, snap = self.historical(ticker, days, methods)
            if mature:
                self.settle(cid, snap)
            snap.update(
                retrieval_policy="sector-v1",
                classification=group(),
                features=features(),
            )
            with s._connect() as conn:
                conn.execute(
                    "UPDATE lab_cases SET snapshot=%s,market=%s WHERE id=%s",
                    (Jsonb(snap), target["market"], cid),
                )
                conn.execute(
                    "UPDATE lab_arms SET audit=%s WHERE case_id=%s",
                    (Jsonb({"market_input_sha256": "a" * 64}), cid),
                )
                if mature:
                    conn.execute(
                        "UPDATE lab_outcomes SET observed_at=%s WHERE case_id=%s",
                        (snap["exit_close_at"], cid),
                    )
                    conn.execute(
                        "UPDATE lab_memories SET created_at=%s WHERE case_id=%s",
                        (snap["exit_close_at"], cid),
                    )
            return cid

        source_ids = [
            historic("X", day, [("single", 0.5, "v1", None)]) for day in (84, 70)
        ]
        older, newer = [s.detail(cid)["memory"]["id"] for cid in source_ids]
        early = historic("X", 42, [("single", 0.5, "v1", None)], False)
        pair = historic(
            "Y", 28, [("single", 0.5, "v1", None), ("memory_sector", 0.9, "v1", older)]
        )
        self.assertEqual(s.select_memory(early, "memory_sector")["id"], newer)
        later = s.create_case(target)
        arm = dict(
            probability=0.5,
            rationale="fixture",
            model="fixed-model",
            version="v1",
            audit={"market_input_sha256": "b" * 64},
        )
        s.record_arm(later, "single", **arm)
        learned = s.select_memory(later, "memory_sector")
        self.assertEqual((learned["id"], learned["uplift_support"]), (older, 1))
        self.assertAlmostEqual(learned["shrunk_uplift"], 0.24 / 6)
        unchanged = s.select_memory(later, "memory")
        self.assertEqual((unchanged["id"], unchanged["uplift_support"]), (newer, 0))
        # Removing matching historical inputs neutralizes the treatment; no extra model call is justified.
        with s._connect() as conn:
            conn.execute(
                "UPDATE lab_arms SET audit='{}' WHERE case_id=%s AND method='memory_sector'",
                (pair,),
            )
        self.assertEqual(s.select_memory(later, "memory_sector")["id"], newer)
        s.record_arm(later, "memory", memory_id=newer, **arm)
        self.assertTrue(
            s.record_arm(later, "memory_sector", status="skipped", error="same_memory")
        )
        sector = next(
            r for r in s.detail(later)["arms"] if r["method"] == "memory_sector"
        )
        audit = sector["audit"]["sector_selection_v1"]
        self.assertEqual(
            (audit["control_memory_id"], audit["selected_memory_id"]), (newer, newer)
        )

    def test_reference_requires_matched_horizon_and_prospective_capture(self):
        s = self.store
        snap = self.snapshot("REF")
        cid = s.create_case(snap)
        cal = exchange_calendars.get_calendar(
            "XNYS" if snap["market"] == "us" else "XKRX"
        )
        source_time = cal.session_close(snap["data_session"]).isoformat()
        fields = {
            "source_report_id": 50,
            "ticker": "REF",
            "probability": 0.8,
            "model": "source-model",
            "source_published_at": source_time,
            "data_session": snap["data_session"],
        }
        self.assertIn(cid, [r["id"] for r in s.open_reference_cases()])
        for change in (
            {"ticker": "OTHER"},
            {"data_session": snap["sessions"][0]},
            {"model": ""},
            {"source_report_id": None},
            {"probability": float("nan")},
            {"source_published_at": "2026-01-01"},
            {"source_published_at": snap["entry_open_at"]},
            {
                "source_published_at": (
                    cal.session_open(snap["sessions"][0]) - timedelta(minutes=1)
                ).isoformat()
            },
        ):
            self.assertFalse(s.record_reference(cid, **{**fields, **change}))
        with ThreadPoolExecutor(2) as pool:
            self.assertEqual(
                sorted(pool.map(lambda _: s.record_reference(cid, **fields), range(2))),
                [False, True],
            )
        self.assertNotIn(cid, [r["id"] for r in s.open_reference_cases()])
        self.assertEqual(s.detail(cid)["reference"]["probability"], 0.8)
        self.assertEqual(s.detail(cid)["arms"], [])
        past, ps = self.historical("LATE", 21, [("single", 0.6, "v1", None)])
        hist_cal = exchange_calendars.get_calendar(
            "XNYS" if ps["market"] == "us" else "XKRX"
        )
        hist_time = hist_cal.session_close(ps["data_session"])
        self.assertFalse(
            s.record_reference(
                past,
                **{
                    **fields,
                    "ticker": "LATE",
                    "source_report_id": 51,
                    "data_session": ps["data_session"],
                    "source_published_at": hist_time,
                },
            )
        )
        # Restore a contemporaneously captured witness as a fixture exclusively in private PostgreSQL.
        with s._connect() as conn:
            conn.execute(
                """INSERT INTO lab_references(case_id,experiment_version,source,source_report_id,ticker,
                data_session,probability,model,source_published_at,captured_at)
                SELECT id,experiment_version,'public_report',51,ticker,data_session,.7,'source-model',%s,created_at
                FROM lab_cases WHERE id=%s""",
                (hist_time, past),
            )
        self.settle(past, ps)
        stats = s.stats()
        self.assertEqual(stats["comparisons"], [])
        (reference,) = stats["reference_comparisons"]
        self.assertEqual(reference["n"], 1)
        self.assertEqual(reference["method"], "single")
        self.assertAlmostEqual(reference["improvement"], 0.09 - 0.16)

    def test_archive_cursor_and_target_cohorts_exclude_other_period(self):
        rows = []
        for ticker, days in (("FIRST", 70), ("SECOND", 14)):
            cid, snap = self.historical(
                ticker,
                days,
                [("baseline", 0.5, "v", None), ("single", 0.75, "v", None)],
            )
            self.settle(cid, snap)
            rows.append((cid, snap))
        first, other = rows
        self.assertEqual([r["id"] for r in self.store.recent_cases(1)], [other[0]])
        self.assertEqual(
            [r["id"] for r in self.store.recent_cases(1, before_id=other[0])],
            [first[0]],
        )
        unpublished = self.store.create_case(self.snapshot("UNPUBLISHED"))
        self.assertEqual(self.store.recent_cases(1)[0]["id"], unpublished)
        self.assertEqual(self.store.recent_cases(1, published_only=True)[0]["id"], other[0])
        self.assertEqual(self.store.recent_cases(1, before_id=other[0], published_only=True)[0]["id"], first[0])
        day = first[1]["data_session"]
        filters = {"market": first[1]["market"], "from_date": day, "to_date": day}
        self.assertEqual(
            [r["ticker"] for r in self.store.recent_cases(ticker="first", **filters)],
            ["FIRST"],
        )
        cohort = self.store.stats(**filters)
        self.assertEqual(cohort["counts"]["matured"], 1)
        self.assertEqual(cohort["comparisons"][0]["n"], 1)
        self.assertEqual([r["n"] for r in cohort["calibration"]], [1, 1])
        self.assertEqual(self.store.stats()["comparisons"][0]["n"], 2)
        with self.assertRaises(ValueError):
            self.store.stats(from_date="2026-02-01", to_date="2025-02-01")

    def test_store_rejects_future_benchmark_and_incomparable_settlement_basis(self):
        s = self.store
        snap = self.snapshot("QUALITY")
        future_bar = {**snap["bars"][0], "date": snap["sessions"][0]}
        with self.assertRaises(ValueError):
            s.create_case({**snap, "benchmark": {"bars": [future_bar]}})
        cid, ps = self.historical("HISTORY", 35, [("single", 0.5, "v", None)])
        clean = {**ps["bars"][0], "close": 110, "high": 115}
        days = ps["sessions"]
        for src, bar in (
            ("different", clean),
            ("fixture", {**clean, "adjustment_uncertain": True}),
            ("fixture", {**clean, "volume": 0}),
        ):
            evidence = {
                "source": src,
                "observed_at": datetime.now(UTC).isoformat(),
                "evidence": {
                    "sessions": days,
                    "bars": [{**bar, "date": d} for d in days],
                },
            }
            with self.assertRaises(ValueError):
                s.record_outcome(cid, entry_open=100, exit_close=110, evidence=evidence)
        self.assertIsNone(s.detail(cid)["outcome"])
